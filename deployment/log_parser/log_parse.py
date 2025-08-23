import pg8000.dbapi
import re
from datetime import datetime
import pytz

# Regular expression pattern to parse log lines
log_pattern = re.compile(
    r'(?P<ip>\S+) \S+ \S+ \[(?P<datetime>[^\]]+)\] "(?P<request>[^"]+)" '
    r'(?P<status>\d+) (?P<size>\S+) "(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
)


def parse_log_line(line):
    """
    Parse a single line from the access log and return a dictionary of fields.
    """
    match = log_pattern.match(line)
    if not match:
        return None
    groups = match.groupdict()
    ip = groups['ip']
    datetime_str = groups['datetime']
    request = groups['request']
    status = groups['status']
    size = groups['size']
    referrer = groups['referrer']
    user_agent = groups['user_agent']

    # Parse datetime
    # Example: '18/Sep/2024:06:52:03 +0000'
    datetime_format = '%d/%b/%Y:%H:%M:%S %z'
    log_datetime = datetime.strptime(datetime_str, datetime_format)

    # Parse request
    # Example: 'GET /bridgectl_setup.py HTTP/1.1'
    request_parts = request.split()
    if len(request_parts) != 3:
        method = ''
        path = ''
        protocol = ''
    else:
        method, path, protocol = request_parts

    # Convert status and size
    status_code = int(status)
    try:
        bytes_sent = int(size)
    except ValueError:
        bytes_sent = 0  # Handle cases where size is '-'

    return {
        'ip_address': ip,
        'log_datetime': log_datetime,
        'method': method,
        'path': path,
        'protocol': protocol,
        'status_code': status_code,
        'bytes_sent': bytes_sent,
        'referrer': referrer,
        'user_agent': user_agent
    }


def process_logs():
    """
    Process the access log file, parse new entries, and insert them into the database.
    """
    # Database connection parameters
    conn_params = {
        'host': 'localhost',
        'port': 5432,
        'user': 'log_user',
        'password': 'log_password',
        'database': 'logs_db',
    }

    # Connect to the database
    conn = pg8000.dbapi.connect(**conn_params)
    cursor = conn.cursor()

    # Get the max log_datetime from the database
    cursor.execute("SELECT MAX(log_datetime) FROM access_logs;")
    result = cursor.fetchone()
    if result and result[0]:
        max_log_datetime = result[0]
    else:
        max_log_datetime = datetime.min.replace(tzinfo=pytz.UTC)

    # Open and read the log file
    with open('/var/log/httpd/access_log', 'r') as f:
        for line in f:
            log_entry = parse_log_line(line)
            if log_entry is None:
                continue  # Skip lines that can't be parsed
            log_datetime = log_entry['log_datetime']
            if log_datetime > max_log_datetime:
                # Insert into database
                cursor.execute("""
                    INSERT INTO access_logs (
                        ip_address,
                        log_datetime,
                        method,
                        path,
                        protocol,
                        status_code,
                        bytes_sent,
                        referrer,
                        user_agent
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    log_entry['ip_address'],
                    log_entry['log_datetime'],
                    log_entry['method'],
                    log_entry['path'],
                    log_entry['protocol'],
                    log_entry['status_code'],
                    log_entry['bytes_sent'],
                    log_entry['referrer'],
                    log_entry['user_agent']
                ))
    # Commit changes and close connection
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == '__main__':
    process_logs()

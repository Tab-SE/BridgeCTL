import time

class Elapsed:
    def __init__(self):
        self.start_time = time.time()
        self.end_time = None
        self.elapsed_seconds = None

    def stop(self):
        self.end_time = time.time()
        self.elapsed_seconds = self.end_time - self.start_time
        return self.elapsed_seconds # in seconds

#elapsed = Elapsed()
#elapsed()

#time.sleep(2)  # Example: simulating a task that takes 2 seconds

#elapsed_time = elapsed.stop()


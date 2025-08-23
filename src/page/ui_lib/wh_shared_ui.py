
class SharedWhUi:
    @staticmethod
    def show_report_age(cont, is_stale: bool, updated_ago: str):
        s = '<span style="color: orange;font-size: 20px;font-weight: bold;">&nbsp;&nbsp;&nbsp; out-of-date</span>' if is_stale else ''
        cont.html(f"report age: {updated_ago}{s}")


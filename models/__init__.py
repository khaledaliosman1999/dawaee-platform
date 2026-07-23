# ترتيب الاستيراد يتبع سلسلة الربط التسلسلي
from . import medicine             # 1 - جدول أساسي
from . import supplier             # 2 - جدول أساسي
from . import pharmacy             # 3 - جدول أساسي
from . import patient              # 4 - جدول أساسي
from . import stock_inbound        # 5 - يربط 1+2+3
from . import inventory            # 6 - يرجع لـ 5
from . import medicine_booking     # 7 - يرجع لـ 6+4
from . import prescription         # 8 - يرجع لـ 7
from . import dispensing_transaction  # 9 - يرجع لـ 7+8
from . import res_users
from . import report_wizard
from . import medicine_demand_wizard
from . import inventory_report_wizard
from . import expired_bookings_wizard
from . import prescription_report_wizard

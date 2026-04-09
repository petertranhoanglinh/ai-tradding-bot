import traceback
import sys

try:
    from server import screener_vn30_cache
    res = screener_vn30_cache()
    with open('debug_out.txt', 'w', encoding='utf8') as f:
        f.write("SUCCESS:\n" + str(res)[:1000])
except Exception as e:
    with open('debug_out.txt', 'w', encoding='utf8') as f:
        f.write("ERROR:\n" + traceback.format_exc())

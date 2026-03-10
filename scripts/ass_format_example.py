#!/usr/bin/env python3
"""
ASS altyazı formatı örnek snippet'leri.
Pop ve fade animasyonları için override string'leri.
"""
import re

c_pri = "&H00FFFFFF"
c_hi = "&H0000FFFF"
relative_start_ms = 500
pop_end_ms = 650

s1 = f"{{\\r\\c{c_pri}\\fscx100\\fscy100}}{{\\t({relative_start_ms},{relative_start_ms},\\c{c_hi}\\fscx130\\fscy130)\\t({relative_start_ms},{pop_end_ms},\\fscx100\\fscy100)}}Word"
print("pop:", s1)

fade = f"{{\\alpha&HFF&\\t({relative_start_ms},{relative_start_ms+200},\\alpha&H00&)}}Word"
print("fade:", fade)

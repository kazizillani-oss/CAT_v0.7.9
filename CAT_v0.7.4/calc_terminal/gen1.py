import os, sys
B=os.path.dirname(os.path.abspath(__file__))
def W(n,c):
 with open(os.path.join(B,n),'w',encoding='utf-8') as f: f.write(c)
 print(f"Wrote {n}")

from pathlib import Path
import urllib.request, urllib.parse, hashlib, json, datetime, re
R=Path(r'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3').resolve()
O=R/'工作记录/揭晓后对照/首次正确性核查-v001'
D=O/'来源页面';D.mkdir(exist_ok=True)
urls={'展示索引':'https://dxs.moe.gov.cn/zx/hd/sxjm/sxjmlw/2023qgdxssxjmjslwzs/2023gjsbqgdxssxjmjslwzs.shtml','A0127':'https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2023qgdxssxjmjslwzs_2023atlw/231104/1865106.shtml','A092':'https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2023qgdxssxjmjslwzs_2023atlw/231104/1865104.shtml'}
out=[]
for name,url in urls.items():
 try:
  data=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35).read()
  (D/(name+'.html')).write_bytes(data);t=data.decode('utf-8')
  out.append({'id':name,'url':url,'at':datetime.datetime.now().astimezone().isoformat(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'local':(D/(name+'.html')).relative_to(R).as_posix()})
  if name=='展示索引':
   for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',t,re.S):
    if re.search(r'A0?(165|127|92)',m.group(2)):print(re.sub('<[^>]+>','',m.group(2)).strip(),urllib.parse.urljoin(url,m.group(1)))
  else:
   print(name,'image examples',re.findall(r'<img[^>]+>',t)[-5:])
 except Exception as e:out.append({'id':name,'url':url,'error':repr(e)})
(O/'来源页面获取记录-v001.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))


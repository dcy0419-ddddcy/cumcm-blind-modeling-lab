from pathlib import Path
import urllib.request, urllib.parse, hashlib, json, datetime, re, concurrent.futures
from html.parser import HTMLParser
R=Path(r'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3').resolve();O=R/'工作记录/揭晓后对照/首次正确性核查-v001'
class P(HTMLParser):
 def __init__(self):super().__init__();self.images=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='img' and re.search(r'A0?(92|127|165)_页面_\d+',a.get('alt','')):self.images.append(a)
def get(url):
 return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35).read()
urls={'A0165':'https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2023qgdxssxjmjslwzs_2023atlw/231104/1865112.shtml','A0127':'https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2023qgdxssxjmjslwzs_2023atlw/231104/1865106.shtml','A092':'https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2023qgdxssxjmjslwzs_2023atlw/231104/1865104.shtml'}
for name,url in urls.items():
 hp=O/'来源页面'/f'{name}.html'
 if not hp.exists():hp.write_bytes(get(url))
 p=P();p.feed(hp.read_text(encoding='utf-8'))
 pages={int(re.search(r'_页面_(\d+)',i['alt']).group(1)):i for i in p.images}
 folder=O/'参考论文'/name;folder.mkdir(parents=True,exist_ok=True)
 def job(item):
  n,i=item;dest=folder/f'page-{n:02d}.jpg';at=datetime.datetime.now().astimezone().isoformat()
  try:
   if not dest.exists():dest.write_bytes(get(i['src']))
   data=dest.read_bytes()
   return {'page':n,'url':i['src'],'alt':i['alt'],'local':dest.relative_to(R).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'retrieved_at':at}
  except Exception as e:return {'page':n,'url':i['src'],'error':repr(e),'retrieved_at':at}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:res=list(ex.map(job,sorted(pages.items())))
 manifest={'reference_id':name,'source_page':url,'source_sha256':hashlib.sha256(hp.read_bytes()).hexdigest(),'source_publication_date':'2023-11-04','selection_basis':'中国大学生在线全国组委会官方展示页面的全部三篇A题论文；选择先于结果阅读','acquired_pages':res,'actually_read_pages':[],'third_party_code_executed':False,'redistribution':'仅本地个人核对留存；网站注明未经书面许可勿转载'}
 (folder/'获取清单-v001.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'id':name,'page_count':len(res),'failed':[r for r in res if 'error'in r]},ensure_ascii=False),flush=True)


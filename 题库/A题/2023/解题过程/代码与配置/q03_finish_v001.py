"""Post-confirmation artifacts. No design changes or optical evaluations."""
import time
START=time.perf_counter()
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q03_common_v001 as io

def main():
    stage=sys.argv[1]
    budget=io.Budget('post_'+stage,'confirmation',START)
    try:
        if stage=='figures':
            import q03_figures_v002 as module
            result=module.run()
        elif stage=='paper':
            import q03_paper_finalize_v001 as module
            result=module.run()
        elif stage=='records':
            import q03_records_v001 as module
            result=module.run(budget)
        else:raise ValueError(stage)
        budget.finish()
        print(json.dumps(io.convert(result),ensure_ascii=False))
    except BaseException as exc:
        budget.finish('FAILED')
        io.event('failures.jsonl',{'stage':'post_'+stage,'type':type(exc).__name__,'message':str(exc),'time':io.now()})
        raise
if __name__=='__main__':main()

import argparse
from .config import JobConfig
from .pipeline import run

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--queries", type=int, default=8)
    p.add_argument("--results-per-query", type=int, default=5)
    args = p.parse_args()
    jobs, packages = run(JobConfig(), args.queries, args.results_per_query)
    print(f"Found {len(jobs)} unique jobs; {len(packages)} qualified for review.")
    for j in jobs[:20]:
        print(f"{j.match_score:.0%} | {j.work_mode:7} | {j.currency:3} | {j.title} | {j.url}")

if __name__ == "__main__":
    main()

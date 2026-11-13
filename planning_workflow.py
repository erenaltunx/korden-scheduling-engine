"""End-to-end external CSV -> universal model -> MILP -> SQL/BI pipeline."""
import argparse
import json
from pathlib import Path
from korden.data_pipeline import load_planning_directory,export_reporting
from korden.universal import normalize_universal
from korden.service import compare


def main():
    parser=argparse.ArgumentParser(description='KORDEN ERP-style CSV planning and reporting')
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--industry',default='Service operations')
    parser.add_argument('--name',default='Imported operational planning workload')
    parser.add_argument('--time-unit',choices=['minute','hour'],default='hour')
    parser.add_argument('--out',type=Path,default=Path('artifacts/enterprise_demo'))
    parser.add_argument('--time-limit',type=float,default=10)
    args=parser.parse_args()
    source=load_planning_directory(args.data_dir,name=args.name,industry=args.industry,time_unit=args.time_unit)
    scenario=normalize_universal(source)
    result=compare(scenario,time_limit=args.time_limit)
    output=export_reporting(source,result,args.out)
    print(json.dumps({'metrics':{'baseline':result['baseline']['metrics'],
        'optimized':result['optimized']['metrics']},'solver':result['solver'],
        'reporting':output},indent=2))

if __name__=='__main__':
    main()

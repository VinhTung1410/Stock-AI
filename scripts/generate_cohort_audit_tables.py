import sys

import pandas as pd

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def generate_markdown_tables():
    # Load directly from verified PIT cohort CSV
    df = pd.read_csv('cohort_audit_39_rows_with_adv20.csv')
    
    # 1. Cohort 16/10
    sub16 = df[df['cohort_date'] == '2026-10-16']
    watch16 = sub16[sub16['decision'] == 'WATCH'].copy().sort_values('symbol')
    
    print("### BẢNG 1: TẬP WATCH COHORT 16/10/2026 (N = %d) - POINT-IN-TIME ADV20\n" % len(watch16))
    print("| Mã | Quyết định | Close T0 | Open T+1 (ATO) | Close T+1 | Exec T+1 (%) | Close T+3 | Exec T+3 (%) | Close T+5 | Exec T+5 (%) | ADV20 PIT (tỷ) |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for _, r in watch16.iterrows():
        t5_close_str = f"{r['close_t5']:.2f}" if pd.notnull(r['close_t5']) else "N/A"
        t5_exec_str = f"{r['exec_t5_pct']:+.2f}%" if pd.notnull(r['exec_t5_pct']) else "N/A"
        print(f"| **{r['symbol']}** | {r['decision']} | {r['close_t0']:.2f} | {r['open_t1']:.2f} | {r['close_t1']:.2f} | **{r['exec_t1_pct']:+.2f}%** | {r['close_t3']:.2f} | {r['exec_t3_pct']:+.2f}% | {t5_close_str} | {t5_exec_str} | {r['adv20_value']:.2f} |")
    
    m_t1 = watch16['exec_t1_pct'].mean()
    m_t3 = watch16['exec_t3_pct'].mean()
    m_t5 = watch16['exec_t5_pct'].dropna().mean()
    print(f"| **TRUNG BÌNH (WATCH)** | - | - | - | - | **{m_t1:+.2f}%** | - | **{m_t3:+.2f}%** | - | **{m_t5:+.2f}%** | - |\n")

    # Key rejected symbols on 16/10 (e.g. FMC, GIL, TCB, VPB)
    rej16 = sub16[sub16['decision'] == 'REJECT'].copy().sort_values('symbol')
    print("#### Các mã REJECT / Quan sát thêm đối chứng ngày 16/10:\n")
    print("| Mã | Quyết định | Close T0 | Open T+1 (ATO) | Close T+1 | Exec T+1 (%) | Close T+3 | Exec T+3 (%) | Close T+5 | Exec T+5 (%) | ADV20 PIT (tỷ) |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for _, r in rej16.iterrows():
        t5_close_str = f"{r['close_t5']:.2f}" if pd.notnull(r['close_t5']) else "N/A"
        t5_exec_str = f"{r['exec_t5_pct']:+.2f}%" if pd.notnull(r['exec_t5_pct']) else "N/A"
        print(f"| **{r['symbol']}** | {r['decision']} | {r['close_t0']:.2f} | {r['open_t1']:.2f} | {r['close_t1']:.2f} | **{r['exec_t1_pct']:+.2f}%** | {r['close_t3']:.2f} | {r['exec_t3_pct']:+.2f}% | {t5_close_str} | {t5_exec_str} | {r['adv20_value']:.2f} |")
    print("\n" + "="*80 + "\n")

    # 2. Cohort 19/10
    sub19 = df[df['cohort_date'] == '2026-10-19']
    watch19 = sub19[sub19['decision'] == 'WATCH'].copy().sort_values('symbol')
    print("### BẢNG 2: TẬP WATCH COHORT 19/10/2026 (N = %d) - POINT-IN-TIME ADV20\n" % len(watch19))
    print("| Mã | Quyết định | Close T0 | Open T+1 (ATO) | Close T+1 | Exec T+1 (%) | Close T+3 | Exec T+3 (%) | Close T+5 | Exec T+5 (%) | ADV20 PIT (tỷ) |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for _, r in watch19.iterrows():
        t5_close_str = f"{r['close_t5']:.2f}" if pd.notnull(r['close_t5']) else "N/A"
        t5_exec_str = f"{r['exec_t5_pct']:+.2f}%" if pd.notnull(r['exec_t5_pct']) else "N/A"
        print(f"| **{r['symbol']}** | {r['decision']} | {r['close_t0']:.2f} | {r['open_t1']:.2f} | {r['close_t1']:.2f} | **{r['exec_t1_pct']:+.2f}%** | {r['close_t3']:.2f} | {r['exec_t3_pct']:+.2f}% | {t5_close_str} | {t5_exec_str} | {r['adv20_value']:.2f} |")
    
    if len(watch19) > 0:
        m19_t1 = watch19['exec_t1_pct'].mean()
        m19_t3 = watch19['exec_t3_pct'].mean()
        print(f"| **TRUNG BÌNH (WATCH)** | - | - | - | - | **{m19_t1:+.2f}%** | - | **{m19_t3:+.2f}%** | - | N/A | - |\n")

    # Key rejected symbols on 19/10 (FMC, GIL, TCB, VPB)
    rej19 = sub19[sub19['decision'] == 'REJECT'].copy().sort_values('symbol')
    print("#### Các mã REJECT / Đối chứng ngày 19/10 (TCB, VPB, FMC, GIL):\n")
    print("| Mã | Quyết định | Close T0 | Open T+1 (ATO) | Close T+1 | Exec T+1 (%) | Close T+3 | Exec T+3 (%) | Close T+5 | Exec T+5 (%) | ADV20 PIT (tỷ) |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for _, r in rej19.iterrows():
        t5_close_str = f"{r['close_t5']:.2f}" if pd.notnull(r['close_t5']) else "N/A"
        t5_exec_str = f"{r['exec_t5_pct']:+.2f}%" if pd.notnull(r['exec_t5_pct']) else "N/A"
        print(f"| **{r['symbol']}** | {r['decision']} | {r['close_t0']:.2f} | {r['open_t1']:.2f} | {r['close_t1']:.2f} | **{r['exec_t1_pct']:+.2f}%** | {r['close_t3']:.2f} | {r['exec_t3_pct']:+.2f}% | {t5_close_str} | {t5_exec_str} | {r['adv20_value']:.2f} |")

if __name__ == "__main__":
    generate_markdown_tables()

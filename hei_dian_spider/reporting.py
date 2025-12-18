from __future__ import annotations

import html as html_lib
from collections import defaultdict


def build_html_report(report: dict) -> str:
    timestamp = report.get("timestamp") or ""
    seed_url = report.get("seed_url") or ""
    summary = report.get("summary") or {}
    security = report.get("security") or {}
    pages = report.get("pages") or []

    issue_counts: dict[str, int] = defaultdict(int)
    for p in pages:
        for issue in (p.get("issues") or []):
            issue_counts[issue] += 1

    issue_rows = "\n".join(
        f"<tr><td>{html_lib.escape(k)}</td><td class='num'>{v}</td></tr>"
        for k, v in sorted(issue_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )

    def _yn(v: object) -> str:
        return "是" if bool(v) else "否"

    def _fmt_issues(p: dict) -> str:
        issues = p.get("issues") or []
        if not issues:
            return ""
        return ", ".join(html_lib.escape(x) for x in issues)

    page_rows = []
    for p in pages:
        status = p.get("status_code")
        indexable = bool(p.get("indexable"))
        row_class = "ok" if indexable and status == 200 and not (p.get("issues") or []) else "warn"
        page_rows.append(
            "<tr class='{row_class}'>"
            "<td class='mono'><a href='{final_url}' target='_blank' rel='noreferrer'>{final_url}</a></td>"
            "<td class='num'>{status}</td>"
            "<td class='num'>{sec_score}</td>"
            "<td class='center'>{indexable}</td>"
            "<td>{title}</td>"
            "<td class='num'>{desc_len}</td>"
            "<td class='num'>{h1}</td>"
            "<td class='mono'>{canonical}</td>"
            "<td class='num'>{inbound}</td>"
            "<td class='num'>{text_len}</td>"
            "<td class='num'>{depth}</td>"
            "<td>{issues}</td>"
            "</tr>".format(
                row_class=row_class,
                final_url=html_lib.escape(p.get("final_url") or p.get("url") or ""),
                status=html_lib.escape("" if status is None else str(status)),
                sec_score=html_lib.escape("" if p.get("security_score") is None else str(int(p.get("security_score")))),
                indexable=_yn(indexable),
                title=html_lib.escape((p.get("title") or "").strip()),
                desc_len=html_lib.escape(str(int(p.get("meta_description_length") or 0))),
                h1=html_lib.escape(str(len(p.get("h1_tags") or []))),
                canonical=html_lib.escape((p.get("canonical_url") or "").strip()),
                inbound=html_lib.escape(str(int(p.get("inbound_link_count") or 0))),
                text_len=html_lib.escape(str(int(p.get("text_content_length") or 0))),
                depth=html_lib.escape(str(int(p.get("depth") or 0))),
                issues=_fmt_issues(p),
            )
        )

    dup_titles = summary.get("duplicate_titles") or {}
    dup_desc = summary.get("duplicate_meta_descriptions") or {}

    def _render_dupes(title: str, dupes: dict) -> str:
        if not dupes:
            return f"<h2>{html_lib.escape(title)}</h2><p class='muted'>無</p>"
        blocks = []
        for k, urls in sorted(dupes.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            urls_html = "".join(
                f"<li class='mono'><a href='{html_lib.escape(u)}' target='_blank' rel='noreferrer'>{html_lib.escape(u)}</a></li>"
                for u in urls[:20]
            )
            more = "" if len(urls) <= 20 else f"<div class='muted'>… 另外 {len(urls)-20} 筆</div>"
            blocks.append(
                "<details><summary><span class='mono'>{k}</span> "
                "<span class='pill'>{n} 頁</span></summary><ul>{urls}</ul>{more}</details>".format(
                    k=html_lib.escape(k),
                    n=len(urls),
                    urls=urls_html,
                    more=more,
                )
            )
        return f"<h2>{html_lib.escape(title)}</h2>" + "\n".join(blocks)

    avg_sec = security.get("avg_score")
    min_sec = security.get("min_score")
    owasp_hits = security.get("owasp_top10_hits_total") or {}
    sec_finding_counts = security.get("finding_counts") or {}

    owasp_rows = "\n".join(
        f"<tr><td class='mono'>{html_lib.escape(k)}</td><td class='num'>{int(v)}</td></tr>"
        for k, v in sorted(owasp_hits.items(), key=lambda kv: (-int(kv[1] or 0), kv[0]))
    )
    sec_finding_rows = "\n".join(
        f"<tr><td class='mono'>{html_lib.escape(k)}</td><td class='num'>{int(v)}</td></tr>"
        for k, v in sorted(sec_finding_counts.items(), key=lambda kv: (-int(kv[1] or 0), kv[0]))[:30]
    )

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SEO 稽核報告</title>
  <style>
    :root {{
      --bg: #ffffff;
      --card: #ffffff;
      --text: #111827;
      --muted: #6b7280;
      --border: #e5e7eb;
      --header: #0f172a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft JhengHei", "PingFang TC", "Noto Sans CJK TC", system-ui, -apple-system, "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 24px;
    }}
    a {{ color: #2563eb; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    h1 {{ margin: 0 0 8px; font-size: 22px; }}
    h2 {{ margin: 18px 0 10px; font-size: 16px; }}
    .muted {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px;
    }}
    .header {{
      background: var(--header);
      color: #ffffff;
      border: 1px solid rgba(255,255,255,0.18);
    }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }}
    .pill {{ display:inline-block; padding: 2px 8px; border-radius: 999px; border: 1px solid rgba(255,255,255,0.25); color: #e5e7eb; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--border); padding: 8px 8px; vertical-align: top; }}
    th {{ text-align: left; color: var(--muted); font-weight: 600; }}
    td.num, th.num {{ text-align: right; }}
    td.center, th.center {{ text-align: center; }}
    details {{ background: rgba(0,0,0,0.02); border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; margin: 10px 0; }}
    summary {{ cursor: pointer; }}
    ul {{ margin: 8px 0 0 18px; }}
    @media print {{
      * {{
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }}
      body {{ padding: 12px; }}
      a {{ color: #111827; text-decoration: underline; }}
      table {{ font-size: 12px; }}
    }}
  </style>
</head>
<body>
  <div class="card header">
    <h1>SEO 稽核報告 <span class="pill mono">{html_lib.escape(timestamp)}</span></h1>
    <div style="color:#e5e7eb">Seed URL：<span class="mono">{html_lib.escape(seed_url)}</span></div>
  </div>

  <h2>摘要</h2>
  <div class="grid">
    <div class="card"><div class="muted">爬取頁數</div><div class="mono" style="font-size:18px">{int(summary.get("pages_crawled") or 0)}</div></div>
    <div class="card"><div class="muted">非 200 頁面</div><div class="mono" style="font-size:18px">{int(summary.get("non_200") or 0)}</div></div>
    <div class="card"><div class="muted">noindex</div><div class="mono" style="font-size:18px">{int(summary.get("noindex") or 0)}</div></div>
  </div>

  <h2>資安（OWASP Top 10 啟發式）</h2>
  <div class="grid">
    <div class="card"><div class="muted">平均分數</div><div class="mono" style="font-size:18px">{"" if avg_sec is None else int(avg_sec)}</div></div>
    <div class="card"><div class="muted">最低分數</div><div class="mono" style="font-size:18px">{"" if min_sec is None else int(min_sec)}</div></div>
    <div class="card"><div class="muted">資料來源</div><div class="mono" style="font-size:18px">HTTP 標頭 + HTML</div></div>
  </div>

  <h2>OWASP Top 10 Hit 統計</h2>
  <div class="card">
    <table>
      <thead><tr><th>Category</th><th class="num">Hits</th></tr></thead>
      <tbody>
        {owasp_rows if owasp_rows else "<tr><td colspan='2' class='muted'>無</td></tr>"}
      </tbody>
    </table>
    <div class="muted" style="margin-top:8px">註：此為低侵入啟發式檢查（非完整弱點掃描）。</div>
  </div>

  <h2>資安 Findings（Top）</h2>
  <div class="card">
    <table>
      <thead><tr><th>Finding</th><th class="num">Count</th></tr></thead>
      <tbody>
        {sec_finding_rows if sec_finding_rows else "<tr><td colspan='2' class='muted'>無</td></tr>"}
      </tbody>
    </table>
  </div>

  <h2>Issue 統計</h2>
  <div class="card">
    <table>
      <thead><tr><th>Issue</th><th class="num">Count</th></tr></thead>
      <tbody>
        {issue_rows if issue_rows else "<tr><td colspan='2' class='muted'>無</td></tr>"}
      </tbody>
    </table>
  </div>

  <h2>頁面明細</h2>
  <div class="card">
    <table>
      <thead>
        <tr>
          <th>URL</th>
          <th class="num">Status</th>
          <th class="num">Sec</th>
          <th class="center">可索引</th>
          <th>Title</th>
          <th class="num">DescLen</th>
          <th class="num">H1</th>
          <th>Canonical</th>
          <th class="num">Inbound</th>
          <th class="num">TextLen</th>
          <th class="num">Depth</th>
          <th>Issues</th>
        </tr>
      </thead>
      <tbody>
        {"".join(page_rows) if page_rows else "<tr><td colspan='12' class='muted'>無資料</td></tr>"}
      </tbody>
    </table>
  </div>

  {_render_dupes("重複 Title", dup_titles)}
  {_render_dupes("重複 Meta Description", dup_desc)}

  <div class="muted" style="margin-top:16px">
    產生方式：本報告由爬蟲抓取 HTML 後做靜態檢查，請以實際頁面、Search Console 與專業資安掃描為準。
  </div>
</body>
</html>"""

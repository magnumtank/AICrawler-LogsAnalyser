import streamlit as st
import re
from collections import defaultdict
from datetime import datetime, date, timedelta
import pandas as pd
import plotly.express as px

# --- Current AI bot list (2025) ---
AI_BOTS = [
    "GPTBot", "ClaudeBot", "PerplexityBot", "Perplexity-User", "meta-externalagent",
    "facebookexternalhit/1.1", "ChatGPT-User", "ReplicateBot", "RunPodBot", "TimpiBot",
    "TogetherAIBot", "xAI", "YouBot", "Googlebot", "Googlebot-Image", "Googlebot-News",
    "Googlebot-Video", "Googlebot-Desktop", "Googlebot-Smartphone", "GoogleOther",
    "GoogleOther-Image", "GoogleOther-Video", "Bingbot", "MSNBot", "BingPreview",
    "Yahoo! Slurp", "Slurp", "DuckDuckBot", "Baiduspider", "sogou spider", "CCBot",
    "BLEXBot", "MegaIndex.ru", "Sitebulb", "LinkedInBot", "Applebot", "YandexBot"
]

# Regex for parsing common Apache/Nginx log format
LOG_PATTERN = re.compile(
    r'(\S+) (\S+) (\S+) \[([^\]]+)\] "([^"]*)" (\d{3}) (\S+) "([^"]*)" "([^"]*)"'
)

def parse_log_line(line):
    match = LOG_PATTERN.match(line)
    if not match:
        return None
    ip, _, _, date_str, request, status, size, referrer, user_agent = match.groups()
    try:
        date_obj = datetime.strptime(date_str.split()[0], "%d/%b/%Y:%H:%M:%S")
    except:
        date_obj = None
    try:
        page = request.split()[1]
    except:
        page = "-"
    return {
        "ip": ip,
        "date": date_obj,
        "request": request,
        "status": status,
        "size": size,
        "referrer": referrer,
        "user_agent": user_agent,
        "page": page,
    }

def analyze_log(file_content):
    crawler_stats = defaultdict(lambda: defaultdict(int))
    page_stats = defaultdict(lambda: defaultdict(int))
    unique_ips = defaultdict(set)

    for line in file_content.decode("utf-8", errors="ignore").splitlines():
        parsed = parse_log_line(line)
        if parsed:
            ua = parsed["user_agent"]
            for bot in AI_BOTS:
                if bot in ua:
                    if parsed["date"]:
                        date_key = parsed["date"].date()
                    else:
                        date_key = None
                    page = parsed["page"]
                    crawler_stats[bot][date_key] += 1
                    page_stats[bot][page] += 1
                    unique_ips[bot].add(parsed["ip"])
    return crawler_stats, page_stats, unique_ips

# Flatten crawler stats to dataframe for filtering and plotting
def crawler_stats_to_df(crawler_stats):
    rows = []
    for bot, date_counts in crawler_stats.items():
        for dt, count in date_counts.items():
            if dt is not None:
                rows.append({"Bot": bot, "Date": dt, "Hits": count})
    df = pd.DataFrame(rows)
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date'])
    return df

# Flatten page stats to dataframe for plotting top pages
def page_stats_to_df(page_stats):
    rows = []
    for bot, page_counts in page_stats.items():
        for page, count in page_counts.items():
            rows.append({"Bot": bot, "Page": page, "Hits": count})
    df = pd.DataFrame(rows)
    return df

# Streamlit UI and logic
st.title("📊 AI Crawler Log Analyzer with Interactive Filters and Plotly Charts")
st.write("Upload your web server access log to analyze AI bot visits, filter by date, and visualize interactive charts.")

uploaded_file = st.file_uploader("Upload access.log file", type=["log", "txt"])

if uploaded_file:
    with st.spinner("Analyzing log file..."):
        crawler_stats, page_stats, unique_ips = analyze_log(uploaded_file.read())

    df_crawler = crawler_stats_to_df(crawler_stats)
    df_pages = page_stats_to_df(page_stats)

    if df_crawler.empty:
        st.warning("No AI bot crawl data found in the uploaded log.")
    else:
        # Date range filter
        min_date = df_crawler['Date'].min()
        max_date = df_crawler['Date'].max()
        st.sidebar.header("Filter options")
        start_date, end_date = st.sidebar.date_input(
            "Select date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        if start_date > end_date:
            st.sidebar.error("Start date must be before end date.")
        else:
            # Filter dataframe by selected date range
            mask = (df_crawler['Date'] >= pd.to_datetime(start_date)) & (df_crawler['Date'] <= pd.to_datetime(end_date))
            df_filtered = df_crawler.loc[mask]

            # Interactive Plotly line chart: Daily hits by bot
            fig_visits = px.line(
                df_filtered, x='Date', y='Hits', color='Bot',
                title="Daily AI Crawler Visits per Bot",
                labels={"Hits": "Number of Hits"}
            )
            st.plotly_chart(fig_visits, use_container_width=True)

            # Show summary table with totals and unique IPs
            st.subheader("Summary Statistics")
            summary_data = []
            for bot in df_filtered['Bot'].unique():
                total_hits = df_filtered[df_filtered['Bot'] == bot]['Hits'].sum()
                unique_ip_count = len(unique_ips.get(bot, set()))
                summary_data.append({"Bot": bot, "Total Hits": total_hits, "Unique IPs": unique_ip_count})
            st.dataframe(pd.DataFrame(summary_data).sort_values("Total Hits", ascending=False))

            # Show top pages per bot for filtered date range
            st.subheader("Top 5 Crawled Pages by Bot (All Time)")

            # We keep top pages overall because page stats don't have dates by default,
            # but you can extend the script to aggregate page stats by date if needed.
            for bot in df_filtered['Bot'].unique():
                df_bot_pages = df_pages[df_pages['Bot'] == bot]
                if not df_bot_pages.empty:
                    top_pages = df_bot_pages.nlargest(5, 'Hits')
                    fig_pages = px.bar(
                        top_pages, x='Page', y='Hits', title=f"Top 5 Pages Crawled by {bot}",
                        labels={"Hits": "Hits", "Page": "Page URL"}
                    )
                    st.plotly_chart(fig_pages, use_container_width=True)


import type { NewsItem } from "../types";

type NewsCardProps = {
  item: NewsItem;
};

function formatDate(value: string | null): string {
  if (!value) {
    return "Unknown date";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown date";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function stripHtml(value: string): string {
  return value.replace(/<[^>]+>/g, "").trim();
}

export function NewsCard({ item }: NewsCardProps) {
  const summary = stripHtml(item.summary);

  return (
    <article className="news-row">
      <div className="news-row-meta">
        <span className="source-pill">{item.source_name}</span>
        <span className="news-row-date">{formatDate(item.published_at)}</span>
      </div>
      <h2 className="news-row-title">
        <a href={item.link} target="_blank" rel="noreferrer">
          {item.title}
        </a>
      </h2>
      {summary && <p className="news-row-summary">{summary}</p>}
    </article>
  );
}

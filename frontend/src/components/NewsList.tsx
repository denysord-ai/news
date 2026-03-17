import type { NewsItem } from "../types";
import { NewsCard } from "./NewsCard";

type NewsListProps = {
  items: NewsItem[];
};

export function NewsList({ items }: NewsListProps) {
  if (items.length === 0) {
    return <p className="state-message">No news items available.</p>;
  }

  return (
    <section aria-live="polite">
      <ul className="news-list">
        {items.map((item) => (
          <li key={item.id} className="news-list-item">
            <NewsCard item={item} />
          </li>
        ))}
      </ul>
    </section>
  );
}

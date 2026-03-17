export type NewsItem = {
  id: string;
  source_id: string;
  source_name: string;
  title: string;
  link: string;
  summary: string;
  published_at: string | null;
  announced_at?: string | null;
  original_published_at?: string | null;
  updated_at?: string | null;
  author?: string | null;
  tags?: string[] | null;
};

export interface UserProfile {
  userId: string;
  email: string;
  role: string;
  timezone: string;
  summaryTimePref: string;
  language: "en" | "zh";
  emailSummaries: boolean;
  lensCount: number;
  firstSignIn?: boolean;
}

export interface Lens {
  lensId: string;
  name: string;
  topicIds: string[];
  trackedAssetIds: string[];
  createdAt?: string;
  updatedAt?: string;
}

export interface FeedItem {
  articleId: string;
  topicId: string;
  publishedAt: string;
  title: string;
  titleZh?: string | null;
  abstraction: string | null;
  abstractionZh?: string | null;
  excerpt: string;
  source: string;
  url: string;
}

export interface FeedPage {
  items: FeedItem[];
  nextCursor: string | null;
}

export interface AssetMove {
  assetId: string;
  symbol: string;
  move: number;
  open: number;
  close: number;
}

export interface Summary {
  date: string;
  lensId: string;
  body: string;
  assetMoves: AssetMove[];
  rationale: string;
  editedByUser: boolean;
  generatedAt: string | null;
  version: number;
}

export interface Topic {
  topicId: string;
  category: string;
  subgroup: string;
  displayName: string;
  assetIds: string[];
}

export interface Asset {
  assetId: string;
  symbol: string;
  name: string;
  assetClass: string;
  finnhubSymbol: string;
  hasPriceFeed: boolean;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface TopicSuggestion {
  topicIds: string[];
  assetIds: string[];
}

export interface ArticleAttachment {
  articleId: string;
  title: string;
  source: string;
  content: string;
  url: string;
}

export const ARTICLE_DND_TYPE = "application/x-finwing-article";

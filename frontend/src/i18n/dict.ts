export type Lang = "en" | "zh";

// UI string dictionary. Keys are stable; `en` is the source of truth and the
// fallback when a `zh` value is missing.
export const dict = {
  en: {
    // nav / shell
    "nav.lenses": "Lenses",
    "nav.summaries": "Daily Summaries",
    "nav.settings": "Settings",
    "nav.feedback": "Feedback",
    "nav.admin": "Admin",
    "nav.chat": "Chat",
    "nav.signOut": "Sign out",
    "footer.disclaimer":
      "FinWing provides news synthesis for information only — not financial advice.",

    // sign in
    "signin.tagline":
      "Your financial news, gathered, filtered, and summarized — so you keep track without the doom-scroll.",
    "signin.google": "Continue with Google",
    "signin.or": "or",
    "signin.email": "Sign in with email",
    "signin.disclaimer":
      "By continuing you agree this tool provides information only, not financial advice.",

    // onboarding / lens editor
    "onboard.title": "Create your first lens",
    "onboard.subtitle":
      "A lens is a set of topics you want to follow. Describe what you care about and let AI pick the topics, or choose them yourself below.",
    "compose.interestsLabel": "Tell us your interests",
    "compose.interestsHint":
      "In plain words — e.g. “US national debt and the US dollar.” We’ll suggest the relevant topics (and related drivers), which you can then tweak.",
    "compose.interestsPlaceholder": "What are you interested in?",
    "compose.suggest": "✨ Suggest topics",
    "compose.thinking": "Thinking…",
    "compose.suggestedPrefix": "Suggested",
    "compose.topic": "topic",
    "compose.topics": "topics",
    "compose.asset": "asset",
    "compose.assets": "assets",
    "compose.suggestedSuffix": "below — adjust anything you like.",
    "compose.suggestFailed":
      "Couldn’t find matching topics — try describing your interests differently.",
    "lens.name": "Lens name",
    "lens.namePlaceholder": "e.g. Fed policy & gold",
    "lens.topics": "Topics",
    "lens.topicsHint": "these decide which news appears",
    "lens.trackedAssets": "Tracked assets",
    "lens.trackedAssetsHint": "these decide which price moves the summary reports",
    "lens.noAssets": "None — this lens will get a news-only summary.",
    "lens.suggestedFromTopics": "Suggested from your topics:",
    "lens.searchAssets": "Search the asset catalog…",
    "lens.noPriceFeed": "no price feed",
    "lens.create": "Create lens",
    "lens.save": "Save changes",
    "lens.saving": "Saving…",

    // lenses feed
    "feed.loadingLenses": "Loading lenses…",
    "feed.noLenses": "No lenses yet",
    "feed.createInSettings": "Create one in Settings.",
    "feed.loading": "Loading feed…",
    "feed.noNews": "No news yet",
    "feed.noNewsHint":
      "New articles matching this lens will appear here within a minute or two.",
    "feed.aiSummary": "AI summary",
    "feed.dragToChat": "drag to chat",

    // summaries
    "sum.markdownClosed": "Markets closed",
    "sum.edit": "Edit",
    "sum.cancel": "Cancel",
    "sum.save": "Save",
    "sum.saving": "Saving…",
    "sum.conflict":
      "This summary changed elsewhere. Close and reopen to get the latest.",
    "sum.saveFailed": "Could not save.",

    // settings
    "settings.title": "Settings",
    "settings.language": "Language",
    "settings.delivery": "Daily summary delivery",
    "settings.emailSummaries": "Email me daily summaries",
    "settings.emailSummariesHint": "Sent to {email} when each summary is generated.",
    "settings.time": "Time (local)",
    "settings.timezone": "Timezone (IANA)",
    "settings.save": "Save",
    "settings.saving": "Saving…",
    "settings.saved": "Saved.",
    "settings.lenses": "Lenses",
    "settings.newLens": "+ New lens",
    "settings.maxLenses": "Maximum 5 lenses",
    "settings.topicsAssets": "{t} topics · {a} tracked assets",
    "settings.edit": "Edit",
    "settings.delete": "Delete",
    "settings.deleteConfirm": "Delete lens “{name}”? Past summaries are kept.",
    "settings.editLens": "Edit {name}",
    "settings.newLensTitle": "New lens",

    // feedback
    "fb.title": "Feedback",
    "fb.subtitle":
      "Found a bug, hit a limit, or have an idea? Send it here — only the FinWing admin sees this.",
    "fb.placeholder": "What’s on your mind?",
    "fb.send": "Send feedback",
    "fb.sending": "Sending…",
    "fb.sent": "Thanks — your feedback was sent.",
    "fb.failed": "Could not send feedback. Please try again.",

    // chat
    "chat.title": "Chat",
    "chat.empty":
      "Ask anything about your lenses, topics, and recent summaries. Tip: drag a news tile from the feed in here to discuss it.",
    "chat.thinking": "thinking…",
    "chat.placeholder": "Message…",
    "chat.placeholderAttached": "Ask about the attached news…",
    "chat.send": "Send",
    "chat.error": "Sorry — something went wrong. Please try again.",
    "chat.attached": "Attached context",
    "chat.drop": "Drop the news tile to add it as context",

    // admin
    "admin.title": "Admin",
    "admin.totalUsers": "Total users",
    "admin.signinsToday": "Sign-ins today",
    "admin.activeToday": "Active today",
    "admin.feedback": "Feedback",
    "admin.noFeedback": "No feedback yet",

    // misc
    "common.justNow": "just now",
    "common.signingIn": "Signing you in…",
    "common.loading": "Loading FinWing…",
  },

  zh: {
    "nav.lenses": "透镜",
    "nav.summaries": "每日摘要",
    "nav.settings": "设置",
    "nav.feedback": "反馈",
    "nav.admin": "管理",
    "nav.chat": "聊天",
    "nav.signOut": "退出登录",
    "footer.disclaimer": "FinWing 仅提供新闻综述供参考，不构成投资建议。",

    "signin.tagline": "自动收集、筛选并摘要您关注的财经新闻——让您轻松掌握动态。",
    "signin.google": "使用 Google 登录",
    "signin.or": "或",
    "signin.email": "使用邮箱登录",
    "signin.disclaimer": "继续即表示您同意本工具仅提供信息，不构成投资建议。",

    "onboard.title": "创建您的第一个透镜",
    "onboard.subtitle": "透镜是您想跟踪的一组主题。描述您关心的内容，让 AI 为您选择主题，或在下方自行选择。",
    "compose.interestsLabel": "告诉我们您的兴趣",
    "compose.interestsHint": "用日常语言描述——例如“美国国债和美元”。我们会建议相关主题（及相关影响因素），您可以随后调整。",
    "compose.interestsPlaceholder": "您对什么感兴趣？",
    "compose.suggest": "✨ 推荐主题",
    "compose.thinking": "思考中…",
    "compose.suggestedPrefix": "已推荐",
    "compose.topic": "个主题",
    "compose.topics": "个主题",
    "compose.asset": "项资产",
    "compose.assets": "项资产",
    "compose.suggestedSuffix": "，您可以随意调整。",
    "compose.suggestFailed": "未找到匹配的主题——请尝试用不同方式描述您的兴趣。",
    "lens.name": "透镜名称",
    "lens.namePlaceholder": "例如：美联储政策与黄金",
    "lens.topics": "主题",
    "lens.topicsHint": "决定显示哪些新闻",
    "lens.trackedAssets": "跟踪资产",
    "lens.trackedAssetsHint": "决定摘要中报告哪些价格变动",
    "lens.noAssets": "无——该透镜将生成仅新闻摘要。",
    "lens.suggestedFromTopics": "根据您的主题建议：",
    "lens.searchAssets": "搜索资产目录…",
    "lens.noPriceFeed": "无价格源",
    "lens.create": "创建透镜",
    "lens.save": "保存更改",
    "lens.saving": "保存中…",

    "feed.loadingLenses": "加载透镜中…",
    "feed.noLenses": "尚无透镜",
    "feed.createInSettings": "请在设置中创建。",
    "feed.loading": "加载新闻中…",
    "feed.noNews": "尚无新闻",
    "feed.noNewsHint": "匹配该透镜的新文章将在一两分钟内显示。",
    "feed.aiSummary": "AI 摘要",
    "feed.dragToChat": "拖入聊天",

    "sum.markdownClosed": "休市",
    "sum.edit": "编辑",
    "sum.cancel": "取消",
    "sum.save": "保存",
    "sum.saving": "保存中…",
    "sum.conflict": "该摘要已在别处更改。请关闭后重新打开以获取最新版本。",
    "sum.saveFailed": "保存失败。",

    "settings.title": "设置",
    "settings.language": "语言",
    "settings.delivery": "每日摘要推送",
    "settings.emailSummaries": "通过邮件发送每日摘要",
    "settings.emailSummariesHint": "每份摘要生成后发送至 {email}。",
    "settings.time": "时间（本地）",
    "settings.timezone": "时区（IANA）",
    "settings.save": "保存",
    "settings.saving": "保存中…",
    "settings.saved": "已保存。",
    "settings.lenses": "透镜",
    "settings.newLens": "+ 新建透镜",
    "settings.maxLenses": "最多 5 个透镜",
    "settings.topicsAssets": "{t} 个主题 · {a} 个跟踪资产",
    "settings.edit": "编辑",
    "settings.delete": "删除",
    "settings.deleteConfirm": "删除透镜“{name}”？历史摘要将保留。",
    "settings.editLens": "编辑 {name}",
    "settings.newLensTitle": "新建透镜",

    "fb.title": "反馈",
    "fb.subtitle": "发现问题、遇到限制或有想法？发送到这里——仅 FinWing 管理员可见。",
    "fb.placeholder": "您在想什么？",
    "fb.send": "发送反馈",
    "fb.sending": "发送中…",
    "fb.sent": "谢谢——您的反馈已发送。",
    "fb.failed": "发送反馈失败，请重试。",

    "chat.title": "聊天",
    "chat.empty": "可以询问任何关于您的透镜、主题和近期摘要的问题。提示：从新闻流拖一张新闻卡片进来讨论。",
    "chat.thinking": "思考中…",
    "chat.placeholder": "输入消息…",
    "chat.placeholderAttached": "询问附加的新闻…",
    "chat.send": "发送",
    "chat.error": "抱歉——出现问题，请重试。",
    "chat.attached": "附加上下文",
    "chat.drop": "放下新闻卡片以添加为上下文",

    "admin.title": "管理",
    "admin.totalUsers": "用户总数",
    "admin.signinsToday": "今日登录次数",
    "admin.activeToday": "今日活跃用户",
    "admin.feedback": "反馈",
    "admin.noFeedback": "尚无反馈",

    "common.justNow": "刚刚",
    "common.signingIn": "正在登录…",
    "common.loading": "正在加载 FinWing…",
  },
} as const;

export type TKey = keyof typeof dict.en;

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { resolveLocale, saveLocale, type Locale } from "./i18nStorage";
import { HERO_NAMES_ZH_CN } from "./heroNamesZhCN";

export type { Locale } from "./i18nStorage";

const zhCN = {
  "app.loading": "正在载入比赛数据",
  "app.loadError": "无法载入比赛数据",
  "app.serviceHint": "请确认 FastAPI 服务正在运行",
  "app.retry": "重新连接",
  "app.subtitle": "天梯选人数据分析",
  "app.heroCount": "{heroes} 位英雄 · {ranks} 个分段",
  "nav.main": "主要功能",
  "nav.draft": "选人助手",
  "nav.leaderboard": "英雄排行榜",
  "settings.open": "打开设置",
  "settings.title": "设置",
  "settings.personalization": "个性化设置",
  "settings.proficiency": "英雄熟练度",
  "settings.proficiencyHint": "设置不会与绝活英雄",
  "settings.weights": "系数调整",
  "settings.weightsHint": "调整推荐评分权重",
  "settings.language": "语言",
  "settings.languageHint": "界面显示语言",
  "language.zhCN": "中文",
  "language.en": "English",
  "common.close": "关闭",
  "common.all": "全部",
  "common.search": "搜索",
  "common.hero": "英雄",
  "common.rank": "分段",
  "common.noData": "暂无数据",
  "common.requestFailed": "请求失败，请稍后重试",
  "common.matches": "{count} 场",
  "draft.mobileDraft": "阵容",
  "draft.mobileResults": "推荐",
  "draft.matchSettings": "比赛参数",
  "draft.matchSettingsHint": "筛选当前对局环境",
  "draft.positions": "想玩的位置",
  "draft.composition": "当前阵容",
  "draft.compositionHint": "选择空位后从英雄池添加",
  "draft.allyLineup": "我方阵容",
  "draft.enemyLineup": "敌方阵容",
  "draft.addHero": "添加{side}英雄",
  "draft.removeHero": "移除 {hero}",
  "draft.ally": "我方",
  "draft.enemy": "敌方",
  "draft.heroPool": "英雄池",
  "draft.heroPoolHint": "点击英雄加入{side}",
  "draft.activeSide": "当前选择阵营",
  "draft.searchHero": "搜索英雄名称",
  "draft.recommendations": "推荐英雄",
  "draft.recommendationSummary": "{rank} · 我方 {allies} · 敌方 {enemies} · Top {count}",
  "draft.recommendationCount": "推荐数",
  "draft.calculating": "计算中",
  "draft.calculate": "计算推荐",
  "draft.baseWinRate": "基础胜率",
  "draft.counterContribution": "对位贡献",
  "draft.synergyContribution": "协同贡献",
  "draft.proficiency": "熟练度",
  "draft.rankMatches": "分段场次",
  "draft.addToAllies": "将 {hero} 加入我方",
  "draft.emptyRecommendations": "当前筛选条件下没有可推荐英雄",
  "draft.resultsPagination": "推荐结果分页",
  "draft.previous": "上一页",
  "draft.next": "下一页",
  "draft.page": "第 {current} / {total} 页",
  "attribute.all": "全部",
  "attribute.str": "力量",
  "attribute.agi": "敏捷",
  "attribute.int": "智力",
  "attribute.all_attr": "全才",
  "position.carry": "一号位",
  "position.mid": "中单",
  "position.offlane": "三号位",
  "position.support": "辅助",
  "rank.Herald": "先锋",
  "rank.Guardian": "卫士",
  "rank.Crusader": "中军",
  "rank.Archon": "统帅",
  "rank.Legend": "传奇",
  "rank.Ancient": "万古流芳",
  "rank.Divine": "超凡入圣",
  "rank.Immortal": "冠世一绝",
  "leaderboard.title": "英雄排行榜",
  "leaderboard.allRanks": "全部分段",
  "leaderboard.summary": "{rank} · {matches} 场比赛",
  "leaderboard.loading": "正在读取比赛统计",
  "leaderboard.searchHero": "英雄名称",
  "leaderboard.pickRate": "Pick 率",
  "leaderboard.winRate": "胜率",
  "leaderboard.counters": "对阵克制",
  "leaderboard.counteredBy": "被克制",
  "leaderboard.empty": "没有匹配的英雄",
  "proficiency.title": "个人英雄熟练度",
  "proficiency.summary": "不会 {unplayed} · 还行 {okay} · 绝活 {signature}",
  "proficiency.resetConfirm": "将所有英雄熟练度重置为还行？",
  "proficiency.filter": "筛选熟练度",
  "proficiency.all": "全部熟练度",
  "proficiency.unplayed": "不会",
  "proficiency.okay": "还行",
  "proficiency.signature": "绝活",
  "proficiency.reset": "全部重置",
  "proficiency.table": "英雄熟练度",
  "weights.title": "Draft Score 系数",
  "weights.description": "控制不同数据在推荐结果中的影响程度",
  "weights.alpha.label": "基础胜率",
  "weights.alpha.description": "英雄在当前分段的整体表现",
  "weights.beta.label": "对位克制",
  "weights.beta.description": "面对敌方阵容时的对阵优势",
  "weights.gamma.label": "阵容协同",
  "weights.gamma.description": "与我方已选英雄的组合表现",
  "weights.delta.label": "个人熟练度",
  "weights.delta.description": "不会、还行和绝活的个人偏好",
} as const;

export type TranslationKey = keyof typeof zhCN;

const en: Record<TranslationKey, string> = {
  "app.loading": "Loading match data",
  "app.loadError": "Unable to load match data",
  "app.serviceHint": "Make sure the FastAPI service is running",
  "app.retry": "Reconnect",
  "app.subtitle": "Ranked Draft Intelligence",
  "app.heroCount": "{heroes} heroes · {ranks} ranks",
  "nav.main": "Main navigation",
  "nav.draft": "Draft Assistant",
  "nav.leaderboard": "Hero Leaderboard",
  "settings.open": "Open settings",
  "settings.title": "Settings",
  "settings.personalization": "Personalization",
  "settings.proficiency": "Hero Proficiency",
  "settings.proficiencyHint": "Set unplayed and signature heroes",
  "settings.weights": "Score Weights",
  "settings.weightsHint": "Adjust recommendation weights",
  "settings.language": "Language",
  "settings.languageHint": "Interface display language",
  "language.zhCN": "中文",
  "language.en": "English",
  "common.close": "Close",
  "common.all": "All",
  "common.search": "Search",
  "common.hero": "Hero",
  "common.rank": "Rank",
  "common.noData": "No data",
  "common.requestFailed": "Request failed. Please try again.",
  "common.matches": "{count} matches",
  "draft.mobileDraft": "Draft",
  "draft.mobileResults": "Results",
  "draft.matchSettings": "Match Settings",
  "draft.matchSettingsHint": "Filter the current match environment",
  "draft.positions": "Preferred Positions",
  "draft.composition": "Current Draft",
  "draft.compositionHint": "Select a slot, then add from the hero pool",
  "draft.allyLineup": "Allied Lineup",
  "draft.enemyLineup": "Enemy Lineup",
  "draft.addHero": "Add {side} hero",
  "draft.removeHero": "Remove {hero}",
  "draft.ally": "Allies",
  "draft.enemy": "Enemies",
  "draft.heroPool": "Hero Pool",
  "draft.heroPoolHint": "Click a hero to add to {side}",
  "draft.activeSide": "Active draft side",
  "draft.searchHero": "Search hero name",
  "draft.recommendations": "Recommended Heroes",
  "draft.recommendationSummary": "{rank} · Allies {allies} · Enemies {enemies} · Top {count}",
  "draft.recommendationCount": "Results",
  "draft.calculating": "Calculating",
  "draft.calculate": "Calculate",
  "draft.baseWinRate": "Base Win Rate",
  "draft.counterContribution": "Counter",
  "draft.synergyContribution": "Synergy",
  "draft.proficiency": "Proficiency",
  "draft.rankMatches": "Rank Matches",
  "draft.addToAllies": "Add {hero} to allies",
  "draft.emptyRecommendations": "No heroes match the current filters",
  "draft.resultsPagination": "Recommendation pages",
  "draft.previous": "Previous",
  "draft.next": "Next",
  "draft.page": "Page {current} of {total}",
  "attribute.all": "All",
  "attribute.str": "Strength",
  "attribute.agi": "Agility",
  "attribute.int": "Intelligence",
  "attribute.all_attr": "Universal",
  "position.carry": "Carry",
  "position.mid": "Mid",
  "position.offlane": "Offlane",
  "position.support": "Support",
  "rank.Herald": "Herald",
  "rank.Guardian": "Guardian",
  "rank.Crusader": "Crusader",
  "rank.Archon": "Archon",
  "rank.Legend": "Legend",
  "rank.Ancient": "Ancient",
  "rank.Divine": "Divine",
  "rank.Immortal": "Immortal",
  "leaderboard.title": "Hero Leaderboard",
  "leaderboard.allRanks": "All Ranks",
  "leaderboard.summary": "{rank} · {matches} matches",
  "leaderboard.loading": "Loading match statistics",
  "leaderboard.searchHero": "Hero name",
  "leaderboard.pickRate": "Pick Rate",
  "leaderboard.winRate": "Win Rate",
  "leaderboard.counters": "Counters",
  "leaderboard.counteredBy": "Countered By",
  "leaderboard.empty": "No matching heroes",
  "proficiency.title": "Hero Proficiency",
  "proficiency.summary": "Unplayed {unplayed} · Comfortable {okay} · Signature {signature}",
  "proficiency.resetConfirm": "Reset every hero's proficiency to Comfortable?",
  "proficiency.filter": "Filter proficiency",
  "proficiency.all": "All Proficiencies",
  "proficiency.unplayed": "Unplayed",
  "proficiency.okay": "Comfortable",
  "proficiency.signature": "Signature",
  "proficiency.reset": "Reset All",
  "proficiency.table": "Hero proficiency",
  "weights.title": "Draft Score Weights",
  "weights.description": "Control how each data source affects recommendations",
  "weights.alpha.label": "Base Win Rate",
  "weights.alpha.description": "Overall hero performance in the selected rank",
  "weights.beta.label": "Counters",
  "weights.beta.description": "Matchup advantage against the enemy lineup",
  "weights.gamma.label": "Synergy",
  "weights.gamma.description": "Performance with the selected allied heroes",
  "weights.delta.label": "Proficiency",
  "weights.delta.description": "Your unplayed, comfortable, and signature preferences",
};

const messages: Record<Locale, Record<TranslationKey, string>> = { "zh-CN": zhCN, en };

type TranslationValues = Record<string, string | number>;

interface I18nContextValue {
  locale: Locale;
  numberLocale: string;
  setLocale: (locale: Locale) => void;
  t: (key: TranslationKey, values?: TranslationValues) => string;
  heroName: (heroId: number, fallback: string) => string;
  rankName: (rank: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

const rankKeys: Record<string, TranslationKey> = {
  Herald: "rank.Herald",
  Guardian: "rank.Guardian",
  Crusader: "rank.Crusader",
  Archon: "rank.Archon",
  Legend: "rank.Legend",
  Ancient: "rank.Ancient",
  Divine: "rank.Divine",
  Immortal: "rank.Immortal",
};

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => resolveLocale());

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((nextLocale: Locale) => {
    setLocaleState(nextLocale);
    saveLocale(nextLocale);
  }, []);

  const t = useCallback((key: TranslationKey, values: TranslationValues = {}) => {
    return messages[locale][key].replace(/\{(\w+)\}/g, (match, name: string) => (
      values[name] === undefined ? match : String(values[name])
    ));
  }, [locale]);

  const heroName = useCallback((heroId: number, fallback: string) => (
    locale === "zh-CN" ? HERO_NAMES_ZH_CN[heroId] ?? fallback : fallback
  ), [locale]);

  const rankName = useCallback((rank: string) => {
    const key = rankKeys[rank];
    return key ? messages[locale][key] : rank;
  }, [locale]);

  const value = useMemo<I18nContextValue>(() => ({
    locale,
    numberLocale: locale === "en" ? "en-US" : "zh-CN",
    setLocale,
    t,
    heroName,
    rankName,
  }), [heroName, locale, rankName, setLocale, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used within I18nProvider");
  return context;
}

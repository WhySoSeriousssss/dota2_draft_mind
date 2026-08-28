export type Locale = "zh-CN" | "en";

export const LANGUAGE_PREFERENCE_KEY = "dota2-draft-mind:language:v1";

export function resolveLocale(storage: Storage = window.localStorage): Locale {
  try {
    return storage.getItem(LANGUAGE_PREFERENCE_KEY) === "en" ? "en" : "zh-CN";
  } catch {
    return "zh-CN";
  }
}

export function saveLocale(locale: Locale, storage: Storage = window.localStorage) {
  try {
    storage.setItem(LANGUAGE_PREFERENCE_KEY, locale);
  } catch {
    return false;
  }
  return true;
}

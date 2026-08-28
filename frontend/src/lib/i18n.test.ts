import { LANGUAGE_PREFERENCE_KEY, resolveLocale } from "./i18nStorage";
import { HERO_NAMES_ZH_CN } from "./heroNamesZhCN";

describe("language preference", () => {
  beforeEach(() => window.localStorage.clear());

  it("defaults to Chinese", () => {
    expect(resolveLocale()).toBe("zh-CN");
  });

  it("restores English and ignores unsupported values", () => {
    window.localStorage.setItem(LANGUAGE_PREFERENCE_KEY, "en");
    expect(resolveLocale()).toBe("en");

    window.localStorage.setItem(LANGUAGE_PREFERENCE_KEY, "fr");
    expect(resolveLocale()).toBe("zh-CN");
  });

  it("contains a Chinese name for every current hero", () => {
    expect(Object.keys(HERO_NAMES_ZH_CN)).toHaveLength(127);
    expect(HERO_NAMES_ZH_CN[25]).toBe("莉娜");
    expect(HERO_NAMES_ZH_CN[155]).toBe("朗戈");
  });
});

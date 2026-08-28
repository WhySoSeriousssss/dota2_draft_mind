import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Brain, ChevronRight, Languages, Settings, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import type { AppConfig } from "../../types/api";
import { useI18n, type Locale } from "../../lib/i18n";
import { ProficiencyDialog } from "./ProficiencyDialog";
import { WeightsDialog } from "./WeightsDialog";

interface SettingsMenuProps {
  config: AppConfig;
}

type OpenDialog = "proficiency" | "weights" | null;

export function SettingsMenu({ config }: SettingsMenuProps) {
  const [openDialog, setOpenDialog] = useState<OpenDialog>(null);
  const { locale, setLocale, t } = useI18n();

  const selectLocale = (nextLocale: Locale) => {
    setLocale(nextLocale);
  };

  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger className="settings-trigger" aria-label={t("settings.open")}>
          <Settings size={17} />
          <span>{t("settings.title")}</span>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content className="settings-dropdown" align="end" sideOffset={8}>
            <DropdownMenu.Label>{t("settings.personalization")}</DropdownMenu.Label>
            <DropdownMenu.Separator />
            <DropdownMenu.Item onSelect={() => setOpenDialog("proficiency")}>
              <span className="menu-item-icon"><Brain size={16} /></span>
              <span><strong>{t("settings.proficiency")}</strong><small>{t("settings.proficiencyHint")}</small></span>
              <ChevronRight size={15} />
            </DropdownMenu.Item>
            <DropdownMenu.Item onSelect={() => setOpenDialog("weights")}>
              <span className="menu-item-icon"><SlidersHorizontal size={16} /></span>
              <span><strong>{t("settings.weights")}</strong><small>{t("settings.weightsHint")}</small></span>
              <ChevronRight size={15} />
            </DropdownMenu.Item>
            <DropdownMenu.Separator />
            <div className="language-setting">
              <span className="menu-item-icon"><Languages size={16} /></span>
              <span><strong>{t("settings.language")}</strong><small>{t("settings.languageHint")}</small></span>
              <div className="language-options" aria-label={t("settings.language")}>
                <button type="button" className={locale === "zh-CN" ? "active" : ""} onClick={() => selectLocale("zh-CN")}>{t("language.zhCN")}</button>
                <button type="button" className={locale === "en" ? "active" : ""} onClick={() => selectLocale("en")}>{t("language.en")}</button>
              </div>
            </div>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      <ProficiencyDialog
        config={config}
        open={openDialog === "proficiency"}
        onOpenChange={(open) => setOpenDialog(open ? "proficiency" : null)}
      />
      <WeightsDialog
        open={openDialog === "weights"}
        onOpenChange={(open) => setOpenDialog(open ? "weights" : null)}
      />
    </>
  );
}

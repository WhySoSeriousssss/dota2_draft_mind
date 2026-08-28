import * as Dialog from "@radix-ui/react-dialog";
import { RotateCcw, Search, X } from "lucide-react";
import { useMemo, useState } from "react";

import { HeroImage } from "../HeroImage";
import { useI18n } from "../../lib/i18n";
import { useDraftStore } from "../../store/draftStore";
import type { AppConfig, Proficiency } from "../../types/api";

interface ProficiencyDialogProps {
  config: AppConfig;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const levels: Proficiency[] = [-1, 0, 1];

export function ProficiencyDialog({ config, open, onOpenChange }: ProficiencyDialogProps) {
  const { heroName, t } = useI18n();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "-1" | "0" | "1">("all");
  const proficiencies = useDraftStore((state) => state.proficiencies);
  const setProficiency = useDraftStore((state) => state.setProficiency);
  const resetProficiencies = useDraftStore((state) => state.resetProficiencies);

  const counts = useMemo(() => {
    const values = Object.values(proficiencies);
    const unplayed = values.filter((value) => value === -1).length;
    const signature = values.filter((value) => value === 1).length;
    return { unplayed, okay: config.heroes.length - unplayed - signature, signature };
  }, [config.heroes.length, proficiencies]);

  const heroes = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    const filterValue = filter === "all" ? null : Number(filter);
    return config.heroes.filter((hero) => {
      const proficiency = proficiencies[hero.id] ?? 0;
      const matchesFilter = filterValue === null || proficiency === filterValue;
      const matchesSearch = !normalizedSearch
        || hero.name.toLowerCase().includes(normalizedSearch)
        || heroName(hero.id, hero.name).toLowerCase().includes(normalizedSearch)
        || String(hero.id) === normalizedSearch;
      return matchesFilter && matchesSearch;
    });
  }, [config.heroes, filter, heroName, proficiencies, search]);

  const resetAll = () => {
    if (Object.keys(proficiencies).length && window.confirm(t("proficiency.resetConfirm"))) {
      resetProficiencies();
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content proficiency-dialog">
          <header className="dialog-header">
            <div>
              <Dialog.Title>{t("proficiency.title")}</Dialog.Title>
              <Dialog.Description>
                {t("proficiency.summary", counts)}
              </Dialog.Description>
            </div>
            <Dialog.Close className="icon-button" aria-label={t("common.close")}>
              <X size={18} />
            </Dialog.Close>
          </header>

          <div className="proficiency-toolbar">
            <label className="search-field proficiency-search">
              <Search size={15} />
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t("draft.searchHero")}
              />
            </label>
            <select
              className="control-select proficiency-filter"
              value={filter}
              onChange={(event) => setFilter(event.target.value as typeof filter)}
              aria-label={t("proficiency.filter")}
            >
              <option value="all">{t("proficiency.all")}</option>
              <option value="-1">{t("proficiency.unplayed")}</option>
              <option value="0">{t("proficiency.okay")}</option>
              <option value="1">{t("proficiency.signature")}</option>
            </select>
            <button className="secondary-button" type="button" onClick={resetAll}>
              <RotateCcw size={15} />
              {t("proficiency.reset")}
            </button>
          </div>

          <div className="proficiency-list" role="table" aria-label={t("proficiency.table")}>
            <div className="proficiency-list-header" role="row">
              <span role="columnheader">{t("common.hero")}</span>
              <span role="columnheader">{t("draft.proficiency")}</span>
            </div>
            <div className="proficiency-list-body">
              {heroes.map((hero) => {
                const current = proficiencies[hero.id] ?? 0;
                const displayName = heroName(hero.id, hero.name);
                return (
                  <div className="proficiency-row" role="row" key={hero.id}>
                    <div className="hero-identity" role="cell">
                      <HeroImage src={hero.image} alt={displayName} />
                      <span><strong>{displayName}</strong><small>ID {hero.id}</small></span>
                    </div>
                    <div className="proficiency-options" role="cell" aria-label={`${displayName} ${t("draft.proficiency")}`}>
                      {levels.map((level) => (
                        <button
                          type="button"
                          key={level}
                          className={current === level ? `active level-${level}` : ""}
                          onClick={() => setProficiency(hero.id, level)}
                        >
                          {level === -1 ? t("proficiency.unplayed") : level === 0 ? t("proficiency.okay") : t("proficiency.signature")}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
              {!heroes.length && <div className="empty-state compact">{t("leaderboard.empty")}</div>}
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

import * as Dialog from "@radix-ui/react-dialog";
import { RotateCcw, Search, X } from "lucide-react";
import { useMemo, useState } from "react";

import { HeroImage } from "../HeroImage";
import { useDraftStore } from "../../store/draftStore";
import type { AppConfig, Proficiency } from "../../types/api";

interface ProficiencyDialogProps {
  config: AppConfig;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const levels: Array<{ value: Proficiency; label: string }> = [
  { value: -1, label: "不会" },
  { value: 0, label: "还行" },
  { value: 1, label: "绝活" },
];

export function ProficiencyDialog({ config, open, onOpenChange }: ProficiencyDialogProps) {
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
        || String(hero.id) === normalizedSearch;
      return matchesFilter && matchesSearch;
    });
  }, [config.heroes, filter, proficiencies, search]);

  const resetAll = () => {
    if (Object.keys(proficiencies).length && window.confirm("将所有英雄熟练度重置为还行？")) {
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
              <Dialog.Title>个人英雄熟练度</Dialog.Title>
              <Dialog.Description>
                不会 {counts.unplayed} · 还行 {counts.okay} · 绝活 {counts.signature}
              </Dialog.Description>
            </div>
            <Dialog.Close className="icon-button" aria-label="关闭">
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
                placeholder="搜索英雄或 ID"
              />
            </label>
            <select
              className="control-select proficiency-filter"
              value={filter}
              onChange={(event) => setFilter(event.target.value as typeof filter)}
              aria-label="筛选熟练度"
            >
              <option value="all">全部熟练度</option>
              <option value="-1">不会</option>
              <option value="0">还行</option>
              <option value="1">绝活</option>
            </select>
            <button className="secondary-button" type="button" onClick={resetAll}>
              <RotateCcw size={15} />
              全部重置
            </button>
          </div>

          <div className="proficiency-list" role="table" aria-label="英雄熟练度">
            <div className="proficiency-list-header" role="row">
              <span role="columnheader">英雄</span>
              <span role="columnheader">熟练度</span>
            </div>
            <div className="proficiency-list-body">
              {heroes.map((hero) => {
                const current = proficiencies[hero.id] ?? 0;
                return (
                  <div className="proficiency-row" role="row" key={hero.id}>
                    <div className="hero-identity" role="cell">
                      <HeroImage src={hero.image} alt={hero.name} />
                      <span><strong>{hero.name}</strong><small>ID {hero.id}</small></span>
                    </div>
                    <div className="proficiency-options" role="cell" aria-label={`${hero.name} 熟练度`}>
                      {levels.map((level) => (
                        <button
                          type="button"
                          key={level.value}
                          className={current === level.value ? `active level-${level.value}` : ""}
                          onClick={() => setProficiency(hero.id, level.value)}
                        >
                          {level.label}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
              {!heroes.length && <div className="empty-state compact">没有匹配的英雄</div>}
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

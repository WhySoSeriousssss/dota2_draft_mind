import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Brain, ChevronRight, Settings, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import type { AppConfig } from "../../types/api";
import { ProficiencyDialog } from "./ProficiencyDialog";
import { WeightsDialog } from "./WeightsDialog";

interface SettingsMenuProps {
  config: AppConfig;
}

type OpenDialog = "proficiency" | "weights" | null;

export function SettingsMenu({ config }: SettingsMenuProps) {
  const [openDialog, setOpenDialog] = useState<OpenDialog>(null);

  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger className="settings-trigger" aria-label="打开设置">
          <Settings size={17} />
          <span>设置</span>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content className="settings-dropdown" align="end" sideOffset={8}>
            <DropdownMenu.Label>个性化设置</DropdownMenu.Label>
            <DropdownMenu.Separator />
            <DropdownMenu.Item onSelect={() => setOpenDialog("proficiency")}>
              <span className="menu-item-icon"><Brain size={16} /></span>
              <span><strong>英雄熟练度</strong><small>设置不会与绝活英雄</small></span>
              <ChevronRight size={15} />
            </DropdownMenu.Item>
            <DropdownMenu.Item onSelect={() => setOpenDialog("weights")}>
              <span className="menu-item-icon"><SlidersHorizontal size={16} /></span>
              <span><strong>系数调整</strong><small>调整推荐评分权重</small></span>
              <ChevronRight size={15} />
            </DropdownMenu.Item>
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

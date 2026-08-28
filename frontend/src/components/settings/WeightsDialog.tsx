import * as Dialog from "@radix-ui/react-dialog";
import * as Slider from "@radix-ui/react-slider";
import { Activity, Handshake, Shield, Sparkles, X } from "lucide-react";

import { useDraftStore } from "../../store/draftStore";
import { useI18n, type TranslationKey } from "../../lib/i18n";
import type { DraftWeights } from "../../types/api";

interface WeightsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const controls: Array<{
  key: keyof DraftWeights;
  max: number;
  step: number;
  icon: typeof Activity;
}> = [
  { key: "alpha", max: 2, step: 0.05, icon: Activity },
  { key: "beta", max: 2, step: 0.05, icon: Shield },
  { key: "gamma", max: 2, step: 0.05, icon: Handshake },
  { key: "delta", max: 0.2, step: 0.01, icon: Sparkles },
];

const symbols: Record<keyof DraftWeights, string> = {
  alpha: "α",
  beta: "β",
  gamma: "γ",
  delta: "δ",
};

export function WeightsDialog({ open, onOpenChange }: WeightsDialogProps) {
  const { t } = useI18n();
  const weights = useDraftStore((state) => state.weights);
  const setWeight = useDraftStore((state) => state.setWeight);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content weights-dialog">
          <header className="dialog-header">
            <div>
              <Dialog.Title>{t("weights.title")}</Dialog.Title>
              <Dialog.Description>{t("weights.description")}</Dialog.Description>
            </div>
            <Dialog.Close className="icon-button" aria-label={t("common.close")}>
              <X size={18} />
            </Dialog.Close>
          </header>

          <div className="weights-grid">
            {controls.map((control) => {
              const Icon = control.icon;
              const label = t(`weights.${control.key}.label` as TranslationKey);
              const description = t(`weights.${control.key}.description` as TranslationKey);
              return (
                <section className="weight-item" key={control.key}>
                  <div className="weight-item-heading">
                    <span className="weight-icon"><Icon size={17} /></span>
                    <div>
                      <strong>{label}</strong>
                      <span>{description}</span>
                    </div>
                    <output>{symbols[control.key]} {weights[control.key].toFixed(2)}</output>
                  </div>
                  <Slider.Root
                    className="slider-root"
                    value={[weights[control.key]]}
                    min={0}
                    max={control.max}
                    step={control.step}
                    onValueChange={([value]) => setWeight(control.key, value)}
                    aria-label={label}
                  >
                    <Slider.Track className="slider-track">
                      <Slider.Range className="slider-range" />
                    </Slider.Track>
                    <Slider.Thumb className="slider-thumb" />
                  </Slider.Root>
                </section>
              );
            })}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

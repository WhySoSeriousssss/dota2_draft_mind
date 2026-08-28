import * as Dialog from "@radix-ui/react-dialog";
import * as Slider from "@radix-ui/react-slider";
import { Activity, Handshake, Shield, Sparkles, X } from "lucide-react";

import { useDraftStore } from "../../store/draftStore";
import type { DraftWeights } from "../../types/api";

interface WeightsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const controls: Array<{
  key: keyof DraftWeights;
  label: string;
  description: string;
  max: number;
  step: number;
  icon: typeof Activity;
}> = [
  { key: "alpha", label: "基础胜率", description: "英雄在当前分段的整体表现", max: 2, step: 0.05, icon: Activity },
  { key: "beta", label: "对位克制", description: "面对敌方阵容时的对阵优势", max: 2, step: 0.05, icon: Shield },
  { key: "gamma", label: "阵容协同", description: "与我方已选英雄的组合表现", max: 2, step: 0.05, icon: Handshake },
  { key: "delta", label: "个人熟练度", description: "不会、还行和绝活的个人偏好", max: 0.2, step: 0.01, icon: Sparkles },
];

const symbols: Record<keyof DraftWeights, string> = {
  alpha: "α",
  beta: "β",
  gamma: "γ",
  delta: "δ",
};

export function WeightsDialog({ open, onOpenChange }: WeightsDialogProps) {
  const weights = useDraftStore((state) => state.weights);
  const setWeight = useDraftStore((state) => state.setWeight);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content weights-dialog">
          <header className="dialog-header">
            <div>
              <Dialog.Title>Draft Score 系数</Dialog.Title>
              <Dialog.Description>控制不同数据在推荐结果中的影响程度</Dialog.Description>
            </div>
            <Dialog.Close className="icon-button" aria-label="关闭">
              <X size={18} />
            </Dialog.Close>
          </header>

          <div className="weights-grid">
            {controls.map((control) => {
              const Icon = control.icon;
              return (
                <section className="weight-item" key={control.key}>
                  <div className="weight-item-heading">
                    <span className="weight-icon"><Icon size={17} /></span>
                    <div>
                      <strong>{control.label}</strong>
                      <span>{control.description}</span>
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
                    aria-label={control.label}
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

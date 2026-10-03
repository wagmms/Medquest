"use client";

import React, { useState, useEffect, useMemo } from "react";
import { 
  FileText, Plus, Trash2, CheckCircle2, 
  Search, ShieldAlert, Sparkles, Send, Pill
} from "lucide-react";
import { OsceDrugItem, OscePrescriptionItem, OsceSpokenQueueItem, OsceLiveFeedback } from "@/types/api";
import { api } from "@/lib/api";

interface PrescriptionPadProps {
  sessionId: string;
  elapsedSeconds: number;
  onPrescriptionSubmitted: (
    prescriptionText: string, 
    examinerMessage: string, 
    spokenQueue: OsceSpokenQueueItem[],
    guidedFeedback?: OsceLiveFeedback
  ) => void;
  isLoading?: boolean;
}

const FALLBACK_DRUGS: OsceDrugItem[] = [
  {
    id: "adrenalina",
    name: "Adrenalina (Epinefrina 1:1000 - 1 mg/ml)",
    category: "Ressuscitação & Aminas",
    default_dose: "0.5",
    default_unit: "mg",
    routes: ["IM (vasto lateral da coxa)", "EV em bólus (PCR)", "SC", "Nebulização"],
    indications: "Anafilaxia grave (0,01 mg/kg até 0,5mg IM), PCR (1mg EV a cada 3-5min)",
    hints: "Na anafilaxia, via IM no vasto lateral é prioritária. Nunca fazer EV puro fora de PCR."
  },
  {
    id: "noradrenalina",
    name: "Noradrenalina (Hemitartarato 2 mg/ml - ampola 4ml/8mg)",
    category: "Ressuscitação & Aminas",
    default_dose: "0.1",
    default_unit: "mcg/kg/min",
    routes: ["EV em BIC contínua"],
    indications: "Choque séptico refratário a volume, choque distributivo, hipotensão grave",
    hints: "Diluição padrão: 4 ampolas (16mg) em 234 ml SG 5% (64 mcg/ml). Titular para PAM >= 65."
  },
  {
    id: "sf09",
    name: "Soro Fisiológico 0,9% (Cloreto de Sódio) 1000ml",
    category: "Soluções & Expansão Volêmica",
    default_dose: "1000",
    default_unit: "ml",
    routes: ["EV em infusão rápida", "EV contínuo"],
    indications: "Expansão volêmica inicial em choque hipovolêmico, desidratação, cetoacidose diabética (1000-1500 ml na 1ª hora)",
    hints: "Na CAD grave, correr 15 a 20 ml/kg na primeira hora."
  },
  {
    id: "ringers_lactate",
    name: "Ringer Lactato bolsa 1000ml",
    category: "Soluções & Expansão Volêmica",
    default_dose: "1000",
    default_unit: "ml",
    routes: ["EV em infusão rápida"],
    indications: "Ressuscitação balanceada no trauma (ATLS 10ª ed: 1000ml restritivo), sepse, grandes queimados",
    hints: "Menor risco de acidose hiperclorêmica do que o soro fisiológico em grandes volumes."
  },
  {
    id: "tranexamico",
    name: "Ácido Tranexâmico (Transamin) ampola 500mg / 1g",
    category: "Hemostasia & Trauma",
    default_dose: "1",
    default_unit: "g",
    routes: ["EV em bólus de 10 min"],
    indications: "Politrauma grave com choque hemorrágico (CRASH-2: em < 3h 1g EV em 10 min seguido de 1g em 8h); Hemorragia pós-parto",
    hints: "Reduz mortalidade no choque hemorrágico e na atonia uterina se feito precocemente (< 3 horas)."
  },
  {
    id: "aas",
    name: "AAS (Ácido Acetilsalicílico) mastigável 100mg",
    category: "Antiarrítmicos & Cardiovasculares",
    default_dose: "200",
    default_unit: "mg",
    routes: ["VO mastigado", "VO deglutido"],
    indications: "Síndrome Coronariana Aguda (SCA com e sem supra), AVC isquêmico",
    hints: "Dose inicial mastigada de 160 a 325 mg (preferencialmente 200 a 300 mg) para absorção bucal imediata."
  },
  {
    id: "ticagrelor",
    name: "Ticagrelor comprimido 90mg",
    category: "Antiarrítmicos & Cardiovasculares",
    default_dose: "180",
    default_unit: "mg",
    routes: ["VO"],
    indications: "SCA com ou sem supra de ST (dupla antiagregação plaquetária em dose de ataque: 2 cp)",
    hints: "Dose de ataque: 180 mg. Preferido em relação ao clopidogrel na diretriz SBC/ESC."
  },
  {
    id: "enoxaparina",
    name: "Enoxaparina sódica seringa 40mg/60mg/80mg",
    category: "Antiarrítmicos & Cardiovasculares",
    default_dose: "1",
    default_unit: "mg/kg",
    routes: ["SC de 12/12h", "EV em bólus de 30mg (ataque em SCA com supra < 75a)"],
    indications: "Anticoagulação plena em SCA, TEP agudo, TVP",
    hints: "Dose plena: 1 mg/kg SC a cada 12 horas. Ajustar para 1x/dia se ClCr < 30."
  },
  {
    id: "insulina_regular",
    name: "Insulina Regular Humana frasco 100 UI/ml",
    category: "Endócrino & Metabólico",
    default_dose: "0.1",
    default_unit: "U/kg/h",
    routes: ["EV em BIC contínua", "EV em bólus de 0,1 U/kg"],
    indications: "Cetoacidose Diabética, Estado Hiperglicêmico Hiperosmolar, Hipercalemia grave",
    hints: "Diluição clássica: 100 UI em 100 ml de SF 0,9% (1 UI/ml). Checar K+ sérico antes de abrir a infusão!"
  },
  {
    id: "kcl",
    name: "Cloreto de Potássio (KCl 19,1% - ampola 10ml com 25 mEq)",
    category: "Soluções & Expansão Volêmica",
    default_dose: "20",
    default_unit: "mEq",
    routes: ["EV diluído em solução (NUNCA em bólus puro!)"],
    indications: "Reposição de potássio na Cetoacidose Diabética (20-30 mEq/L de soro para manter K+ entre 4 e 5)",
    hints: "AVISO CRÍTICO: KCl puro em bólus é letal por assistolia. Sempre diluir em soro!"
  },
  {
    id: "sulfato_magnesio",
    name: "Sulfato de Magnésio 50% / 10%",
    category: "Ginecologia & Obstetrícia",
    default_dose: "4",
    default_unit: "g",
    routes: ["EV em 15-20 min (ataque)", "EV em BIC a 1-2g/h (manutenção - Zuspan)"],
    indications: "Prevenção e tratamento de Eclâmpsia em gestantes com Pré-Eclâmpsia grave",
    hints: "Regra Zuspan: Ataque 4g EV em 20 min + Manutenção 1 a 2 g/h em BIC contínua."
  },
  {
    id: "ocitocina",
    name: "Ocitocina ampola 5 UI / 10 UI",
    category: "Ginecologia & Obstetrícia",
    default_dose: "10",
    default_unit: "UI",
    routes: ["EV em infusão lenta / bólus lento", "EV diluída em BIC (20-40 UI em 500ml SF)", "IM"],
    indications: "Prevenção e tratamento de primeira linha de Hemorragia Pós-Parto por Atonia Uterina",
    hints: "Primeira droga de escolha para atonia uterina."
  }
];

export function PrescriptionPad({
  sessionId,
  elapsedSeconds,
  onPrescriptionSubmitted,
  isLoading = false
}: PrescriptionPadProps) {
  const [catalog, setCatalog] = useState<OsceDrugItem[]>(FALLBACK_DRUGS);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDrug, setSelectedDrug] = useState<OsceDrugItem | null>(null);

  // Campos do formulário de dosagem
  const [dose, setDose] = useState("");
  const [unit, setUnit] = useState("mg");
  const [route, setRoute] = useState("EV em infusão rápida");
  const [notes, setNotes] = useState("");

  // Lista de itens atualmente na prancheta
  const [prescribedItems, setPrescribedItems] = useState<OscePrescriptionItem[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Carrega o catálogo remoto da API se disponível
  useEffect(() => {
    let isMounted = true;
    api.osce.getDrugs()
      .then((res) => {
        if (isMounted && res?.drugs && res.drugs.length > 0) {
          setCatalog(res.drugs);
        }
      })
      .catch(() => {
        // Mantém fallback local seguro
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Filtro de fármacos com busca tolerante
  const filteredDrugs = useMemo(() => {
    if (!searchQuery.trim()) return catalog.slice(0, 10);
    const q = searchQuery.toLowerCase().trim();
    return catalog.filter((d) => 
      d.name.toLowerCase().includes(q) ||
      d.category.toLowerCase().includes(q) ||
      d.indications.toLowerCase().includes(q)
    );
  }, [catalog, searchQuery]);

  // Ao selecionar um fármaco da busca, pré-preenche os campos
  const handleSelectDrug = (drug: OsceDrugItem) => {
    setSelectedDrug(drug);
    setDose(drug.default_dose);
    setUnit(drug.default_unit);
    setRoute(drug.routes[0] || "EV");
    setNotes(drug.hints || "");
  };

  // Adiciona fármaco à folha de prescrição
  const handleAddItem = () => {
    if (!selectedDrug) return;
    const newItem: OscePrescriptionItem = {
      drug_name: selectedDrug.name,
      dose: dose.trim(),
      unit: unit.trim(),
      route: route.trim(),
      notes: notes.trim() || undefined
    };
    setPrescribedItems((prev) => [...prev, newItem]);
    setSelectedDrug(null);
    setSearchQuery("");
    setDose("");
    setNotes("");
  };

  // Remove item da folha
  const handleRemoveItem = (index: number) => {
    setPrescribedItems((prev) => prev.filter((_, i) => i !== index));
  };

  // Presets Clínicos Rápidos de Urgência
  const applyPreset = (presetName: "sca" | "trauma" | "cad" | "preeclampsia" | "atonia") => {
    if (presetName === "sca") {
      setPrescribedItems([
        { drug_name: "AAS (Ácido Acetilsalicílico) mastigável 100mg", dose: "200", unit: "mg", route: "VO mastigado", notes: "Dose de ataque" },
        { drug_name: "Ticagrelor comprimido 90mg", dose: "180", unit: "mg", route: "VO", notes: "Dose de ataque (2 comprimidos)" },
        { drug_name: "Enoxaparina sódica", dose: "1", unit: "mg/kg", route: "SC de 12/12h", notes: "Anticoagulação plena" }
      ]);
    } else if (presetName === "trauma") {
      setPrescribedItems([
        { drug_name: "Ácido Tranexâmico (Transamin)", dose: "1", unit: "g", route: "EV em bólus de 10 min", notes: "Protocolo CRASH-2 / ATLS (<3h)" },
        { drug_name: "Ringer Lactato", dose: "1000", unit: "ml", route: "EV em infusão rápida", notes: "Ressuscitação balanceada restritiva" }
      ]);
    } else if (presetName === "cad") {
      setPrescribedItems([
        { drug_name: "Soro Fisiológico 0,9%", dose: "1000", unit: "ml", route: "EV em infusão rápida", notes: "1ª hora de expansão (15-20 ml/kg)" },
        { drug_name: "Cloreto de Potássio (KCl 19,1%)", dose: "20", unit: "mEq", route: "EV diluído em solução", notes: "Reposição para manter K+ entre 4 e 5" },
        { drug_name: "Insulina Regular Humana", dose: "0.1", unit: "U/kg/h", route: "EV em BIC contínua", notes: "Meta: queda de 50-70 mg/dL/h" }
      ]);
    } else if (presetName === "preeclampsia") {
      setPrescribedItems([
        { drug_name: "Sulfato de Magnésio 50%", dose: "4", unit: "g", route: "EV em 15-20 min", notes: "Dose de ataque (Esquema Zuspan)" },
        { drug_name: "Sulfato de Magnésio 50%", dose: "1", unit: "g/h", route: "EV em BIC contínua", notes: "Dose de manutenção (Zuspan)" },
        { drug_name: "Hidralazina (Cloridrato)", dose: "5", unit: "mg", route: "EV lento a cada 20 min", notes: "Controle da crise hipertensiva" }
      ]);
    } else if (presetName === "atonia") {
      setPrescribedItems([
        { drug_name: "Ocitocina", dose: "10", unit: "UI", route: "EV em infusão lenta", notes: "1ª linha atonia uterina" },
        { drug_name: "Ácido Tranexâmico", dose: "1", unit: "g", route: "EV em bólus de 10 min", notes: "WOMAN Trial em < 3 horas" },
        { drug_name: "Misoprostol", dose: "800", unit: "mcg", route: "Via retal", notes: "2ª linha após ocitocina" }
      ]);
    }
  };

  // Enviar / Assinar Prescrição
  const handleSubmitPrescription = async () => {
    if (prescribedItems.length === 0 || isSubmitting) return;

    setIsSubmitting(true);
    setSuccessMessage(null);

    try {
      const res = await api.osce.prescribe(sessionId, prescribedItems, elapsedSeconds);
      if (res?.success) {
        setSuccessMessage("Prescrição assinada e administrada pela equipe da Sala Vermelha!");
        onPrescriptionSubmitted(res.prescription_text, res.examiner_message, res.spoken_queue || [], res.guided_feedback);
        // Limpa a prancheta após administrar
        setTimeout(() => {
          setPrescribedItems([]);
          setSuccessMessage(null);
        }, 3500);
      }
    } catch {
      // Erro ao enviar prescrição
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-4 animate-in fade-in duration-200">
      {/* Header da Prancheta */}
      <div className="flex items-center justify-between p-3 rounded-xl bg-card border border-border">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-primary" />
          <span className="font-bold text-xs text-foreground uppercase tracking-wide">
            Prancheta de Prescrição Beira-Leito (Sala Vermelha)
          </span>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-primary/10 text-primary font-bold">
          {prescribedItems.length} fármaco(s) na folha
        </span>
      </div>

      {/* Presets Rápidos de Urgência Canônica de Prova */}
      <div className="space-y-1.5">
        <span className="text-[11px] text-muted-foreground font-semibold flex items-center gap-1">
          <Sparkles className="w-3 h-3 text-amber-500" />
          Protocolos Rápidos de Prova Prática (Clique para carregar):
        </span>
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          <button
            type="button"
            onClick={() => applyPreset("sca")}
            className="px-2 py-1 rounded-lg bg-muted/60 hover:bg-primary/20 hover:text-primary transition-colors border border-border font-medium"
          >
            🫀 SCA / IAM (AAS + Ticagrelor + Enoxaparina)
          </button>
          <button
            type="button"
            onClick={() => applyPreset("trauma")}
            className="px-2 py-1 rounded-lg bg-muted/60 hover:bg-primary/20 hover:text-primary transition-colors border border-border font-medium"
          >
            🩸 Trauma (Ácido Tranexâmico + Ringer)
          </button>
          <button
            type="button"
            onClick={() => applyPreset("cad")}
            className="px-2 py-1 rounded-lg bg-muted/60 hover:bg-primary/20 hover:text-primary transition-colors border border-border font-medium"
          >
            🍬 Cetoacidose (SF 0,9% + KCl + Insulina BIC)
          </button>
          <button
            type="button"
            onClick={() => applyPreset("preeclampsia")}
            className="px-2 py-1 rounded-lg bg-muted/60 hover:bg-primary/20 hover:text-primary transition-colors border border-border font-medium"
          >
            🤰 Pré-Eclâmpsia (Sulfato Zuspan + Hidralazina)
          </button>
          <button
            type="button"
            onClick={() => applyPreset("atonia")}
            className="px-2 py-1 rounded-lg bg-muted/60 hover:bg-primary/20 hover:text-primary transition-colors border border-border font-medium"
          >
            👶 Atonia Uterina (Ocitocina + Tranexâmico + Miso)
          </button>
        </div>
      </div>

      {/* Busca e Seleção de Fármacos */}
      <div className="p-3.5 rounded-xl border border-border bg-card space-y-3">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-3 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Buscar medicamento (ex: Adrenalina, AAS, Soro, Insulina, Tranexâmico, KCl)..."
            className="w-full pl-8 pr-3 py-2 bg-muted/50 border border-border rounded-lg text-xs focus:outline-none focus:border-primary"
          />
        </div>

        {/* Dropdown de Resultados da Busca */}
        {searchQuery.trim() && !selectedDrug && (
          <div className="max-h-40 overflow-y-auto border border-border rounded-lg bg-background divide-y divide-border">
            {filteredDrugs.length === 0 ? (
              <div className="p-2.5 text-xs text-muted-foreground text-center">
                Nenhum medicamento encontrado no catálogo.
              </div>
            ) : (
              filteredDrugs.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => handleSelectDrug(d)}
                  className="w-full p-2 text-left text-xs hover:bg-muted transition-colors flex items-center justify-between"
                >
                  <div>
                    <span className="font-bold text-foreground block">{d.name}</span>
                    <span className="text-[10px] text-muted-foreground">{d.category} • {d.indications}</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-primary/10 text-primary font-mono shrink-0">
                    {d.default_dose} {d.default_unit}
                  </span>
                </button>
              ))
            )}
          </div>
        )}

        {/* Painel de Configuração de Dose do Medicamento Selecionado */}
        {selectedDrug && (
          <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 space-y-2.5 animate-in fade-in">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs text-primary flex items-center gap-1.5">
                <Pill className="w-3.5 h-3.5" />
                {selectedDrug.name}
              </span>
              <button
                type="button"
                onClick={() => setSelectedDrug(null)}
                className="text-[10px] text-muted-foreground hover:text-foreground underline"
              >
                Trocar
              </button>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="text-[10px] font-semibold text-muted-foreground block mb-1">Dose:</label>
                <input
                  type="text"
                  value={dose}
                  onChange={(e) => setDose(e.target.value)}
                  placeholder="Ex: 1000 ou 0.1"
                  className="w-full p-1.5 bg-background border border-border rounded text-xs focus:outline-none focus:border-primary font-mono"
                />
              </div>

              <div>
                <label className="text-[10px] font-semibold text-muted-foreground block mb-1">Unidade:</label>
                <input
                  type="text"
                  value={unit}
                  onChange={(e) => setUnit(e.target.value)}
                  placeholder="mg, g, ml, U/kg/h"
                  className="w-full p-1.5 bg-background border border-border rounded text-xs focus:outline-none focus:border-primary font-mono"
                />
              </div>

              <div>
                <label className="text-[10px] font-semibold text-muted-foreground block mb-1">Via:</label>
                <select
                  value={route}
                  onChange={(e) => setRoute(e.target.value)}
                  className="w-full p-1.5 bg-background border border-border rounded text-xs focus:outline-none focus:border-primary"
                >
                  {selectedDrug.routes.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                  <option value="EV em bólus">EV em bólus</option>
                  <option value="EV em infusão rápida">EV em infusão rápida</option>
                  <option value="EV em BIC contínua">EV em BIC contínua</option>
                  <option value="IM">IM</option>
                  <option value="SC">SC</option>
                  <option value="VO">VO</option>
                  <option value="Inalatória">Inalatória</option>
                </select>
              </div>
            </div>

            <div>
              <label className="text-[10px] font-semibold text-muted-foreground block mb-1">
                Observações / Diluição / Tempo de Infusão:
              </label>
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Ex: correr na primeira hora; vasto lateral da coxa..."
                className="w-full p-1.5 bg-background border border-border rounded text-xs focus:outline-none focus:border-primary"
              />
            </div>

            <button
              type="button"
              onClick={handleAddItem}
              className="w-full py-1.5 rounded-lg bg-primary text-primary-foreground font-bold text-xs flex items-center justify-center gap-1.5 hover:bg-primary/90 transition-transform active:scale-98"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Adicionar à Folha de Prescrição</span>
            </button>
          </div>
        )}
      </div>

      {/* Lista da Folha de Prescrição */}
      <div className="space-y-2">
        <span className="text-[11px] text-muted-foreground font-semibold block">
          Medicamentos na Folha para Assinatura Médica:
        </span>

        {prescribedItems.length === 0 ? (
          <div className="p-4 rounded-xl border border-dashed border-border text-center text-xs text-muted-foreground space-y-1 bg-muted/20">
            <ShieldAlert className="w-4 h-4 mx-auto text-muted-foreground/60" />
            <p>Nenhum fármaco adicionado à prescrição ainda.</p>
            <p className="text-[10px]">Use os protocolos rápidos acima ou busque medicações para prescrever.</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {prescribedItems.map((item, index) => (
              <div
                key={index}
                className="p-2.5 rounded-xl border border-border bg-card flex items-center justify-between text-xs hover:border-primary/30 transition-colors"
              >
                <div className="space-y-0.5">
                  <div className="font-bold text-foreground flex items-center gap-2">
                    <span>{index + 1}. {item.drug_name}</span>
                    <span className="font-mono px-1.5 py-0.5 rounded bg-muted text-[10px] font-semibold text-primary">
                      {item.dose} {item.unit}
                    </span>
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    Via: <span className="font-medium text-foreground">{item.route}</span>
                    {item.notes && <span className="ml-1 italic">({item.notes})</span>}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleRemoveItem(index)}
                  className="p-1 rounded text-muted-foreground hover:text-rose-500 hover:bg-rose-500/10 transition-colors"
                  title="Remover medicamento"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Feedback de Sucesso */}
      {successMessage && (
        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Botão de Enviar e Assinar Prescrição */}
      <button
        type="button"
        onClick={handleSubmitPrescription}
        disabled={prescribedItems.length === 0 || isSubmitting || isLoading}
        className="w-full py-2.5 rounded-xl font-bold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 text-xs shadow-sm flex items-center justify-center gap-2 transition-transform active:scale-98"
      >
        {isSubmitting ? (
          <>
            <span className="w-3.5 h-3.5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin"></span>
            <span>Processando Prescrição na Sala Vermelha...</span>
          </>
        ) : (
          <>
            <Send className="w-3.5 h-3.5" />
            <span>Assinar e Administrar Prescrição Beira-Leito</span>
          </>
        )}
      </button>
    </div>
  );
}

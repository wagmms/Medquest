import { PlannerWeek } from "@/types/api";

declare global {
  interface Window {
    google?: {
      accounts: {
        oauth2: {
          initTokenClient: (config: {
            client_id: string;
            scope: string;
            callback: (response: { access_token?: string; error?: string }) => void;
          }) => {
            requestAccessToken: () => void;
          };
        };
      };
    };
  }
}

export interface SyncProgress {
  current: number;
  total: number;
  status: string;
}

export async function syncPlanToGoogleCalendarDirectly(
  plan: PlannerWeek[],
  daysPerWeek: number = 6,
  onProgress?: (progress: SyncProgress) => void
): Promise<{ success: boolean; calendarId?: string; error?: string }> {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  if (!clientId) {
    throw new Error("GOOGLE_CLIENT_ID_MISSING");
  }

  // Carrega o script Google Identity Services se ainda não estiver presente
  if (!window.google?.accounts?.oauth2) {
    await new Promise<void>((resolve, reject) => {
      const existing = document.querySelector('script[src="https://accounts.google.com/gsi/client"]');
      if (existing) {
        resolve();
        return;
      }
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Falha ao carregar o serviço Google Identity Services"));
      document.body.appendChild(script);
    });
  }

  return new Promise((resolve, reject) => {
    try {
      const tokenClient = window.google!.accounts.oauth2.initTokenClient({
        client_id: clientId,
        scope: "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar",
        callback: async (tokenResponse) => {
          if (tokenResponse.error || !tokenResponse.access_token) {
            return reject(new Error(tokenResponse.error || "Acesso não autorizado pelo usuário"));
          }

          try {
            const accessToken = tokenResponse.access_token;
            onProgress?.({ current: 0, total: 100, status: "Conectando e criando agenda MedQuest..." });

            // 1. Verifica ou cria uma agenda própria editável no Google Calendar
            const calListRes = await fetch("https://www.googleapis.com/calendar/v3/users/me/calendarList", {
              headers: { Authorization: `Bearer ${accessToken}` },
            });
            const calListData = await calListRes.json();
            let targetCalId = "primary";

            const existingCal = calListData.items?.find((c: { summary: string; id: string }) => 
              c.summary === "MedQuest - Cronograma de Residência"
            );

            if (existingCal) {
              targetCalId = existingCal.id;
            } else {
              const createCalRes = await fetch("https://www.googleapis.com/calendar/v3/calendars", {
                method: "POST",
                headers: {
                  Authorization: `Bearer ${accessToken}`,
                  "Content-Type": "application/json",
                },
                body: JSON.stringify({
                  summary: "MedQuest - Cronograma de Residência",
                  description: "Cronograma de estudos e revisões ativas do MedQuest (100% Editável).",
                  timeZone: "America/Sao_Paulo",
                }),
              });
              const newCal = await createCalRes.json();
              if (newCal.id) {
                targetCalId = newCal.id;
              }
            }

            // 2. Prepara todos os eventos de aulas e revisões
            const eventsToInsert: Array<{
              summary: string;
              description: string;
              start: { dateTime: string; timeZone: string };
              end: { dateTime: string; timeZone: string };
            }> = [];

            const origin = typeof window !== "undefined" ? window.location.origin : "";
            const studyDaysCount = Math.max(1, Math.min(7, daysPerWeek));

            for (const week of plan) {
              const weekDate = new Date(week.date);
              for (let tIdx = 0; tIdx < week.topics.length; tIdx++) {
                const topic = week.topics[tIdx];
                const dayOffset = tIdx % studyDaysCount;
                const topicDate = new Date(weekDate.getTime() + dayOffset * 86400000);

                const dtStart = new Date(topicDate);
                dtStart.setHours(8, 0, 0, 0);
                const durationMinutes = Math.max(30, Math.round(topic.estimated_hours * 60));
                const dtEnd = new Date(dtStart.getTime() + durationMinutes * 60000);

                // Evento de Aula
                eventsToInsert.push({
                  summary: `[MedQuest] 📖 ${topic.subtema} (${topic.area})`,
                  description: `📚 Carga: ${topic.estimated_hours}h (Teoria: ${topic.estimated_theory_hours}h + Questões: ${topic.estimated_practice_hours}h)\nSemana ${week.week} • ${topic.area}${origin ? `\n\n🔗 Questões: ${origin}/estudar?subtema=${encodeURIComponent(topic.subtema)}&limit=25` : ""}`,
                  start: { dateTime: dtStart.toISOString(), timeZone: "America/Sao_Paulo" },
                  end: { dateTime: dtEnd.toISOString(), timeZone: "America/Sao_Paulo" },
                });
              }
            }

            // 3. Atualização ou inserção inteligente dos eventos na conta do Google
            let existingEventsMap = new Map<string, string>();
            try {
              const existingEventsRes = await fetch(
                `https://www.googleapis.com/calendar/v3/calendars/${encodeURIComponent(targetCalId)}/events?maxResults=2500`,
                { headers: { Authorization: `Bearer ${accessToken}` } }
              );
              const existingEventsData = await existingEventsRes.json();
              if (Array.isArray(existingEventsData.items)) {
                for (const item of existingEventsData.items) {
                  if (item.summary && item.id) {
                    existingEventsMap.set(item.summary, item.id);
                  }
                }
              }
            } catch {
              existingEventsMap = new Map<string, string>();
            }

            const total = eventsToInsert.length;
            for (let i = 0; i < total; i++) {
              const ev = eventsToInsert[i];
              const existingEventId = existingEventsMap.get(ev.summary);

              onProgress?.({
                current: i + 1,
                total,
                status: existingEventId
                  ? `Atualizando evento ${i + 1} de ${total}: ${ev.summary}...`
                  : `Criando evento ${i + 1} de ${total}: ${ev.summary}...`,
              });

              if (existingEventId) {
                await fetch(
                  `https://www.googleapis.com/calendar/v3/calendars/${encodeURIComponent(targetCalId)}/events/${encodeURIComponent(existingEventId)}`,
                  {
                    method: "PATCH",
                    headers: {
                      Authorization: `Bearer ${accessToken}`,
                      "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                      description: ev.description,
                    }),
                  }
                );
              } else {
                await fetch(
                  `https://www.googleapis.com/calendar/v3/calendars/${encodeURIComponent(targetCalId)}/events`,
                  {
                    method: "POST",
                    headers: {
                      Authorization: `Bearer ${accessToken}`,
                      "Content-Type": "application/json",
                    },
                    body: JSON.stringify(ev),
                  }
                );
              }
            }

            resolve({ success: true, calendarId: targetCalId });
          } catch (err) {
            reject(err);
          }
        },
      });

      tokenClient.requestAccessToken();
    } catch (err) {
      reject(err);
    }
  });
}

// -----------------------------------------------------------------------------------
// ADVANCED TWO-WAY SYNC (Regra de União & Efeito Cascata - Internato Turma J)
// -----------------------------------------------------------------------------------
export async function advancedTwoWaySync(
  plan: PlannerWeek[],
  daysPerWeek: number = 6,
  onProgress?: (progress: SyncProgress) => void
): Promise<{ success: boolean; calendarId?: string; error?: string }> {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  if (!clientId) throw new Error("GOOGLE_CLIENT_ID_MISSING");

  if (!window.google?.accounts?.oauth2) {
    await new Promise<void>((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Falha Identity Services"));
      document.body.appendChild(script);
    });
  }

  return new Promise((resolve, reject) => {
    try {
      const tokenClient = window.google!.accounts.oauth2.initTokenClient({
        client_id: clientId,
        scope: "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar",
        callback: async (response: any) => {
          if (response.error) return reject(new Error(response.error));
          const accessToken = response.access_token;

          try {
            const targetCalId = "primary";
            onProgress?.({ current: 0, total: 100, status: "Analisando estado atual da agenda..." });

            // 1. Fetch Todos os eventos da Agenda
            const res = await fetch(
              `https://www.googleapis.com/calendar/v3/calendars/${encodeURIComponent(targetCalId)}/events?maxResults=2500`,
              { headers: { Authorization: `Bearer ${accessToken}` } }
            );
            const data = await res.json();
            const existingItems = data.items || [];

            const concluidos = new Set<string>();
            const paraDeletar = new Set<string>();

            const now = new Date();

            for (const item of existingItems) {
               if (!item.summary || !item.summary.includes("[MedQuest]")) continue;
               
               const syncId = item.summary.replace("[MedQuest] 📖 ", "").replace("[MedQuest] ✍️ ", "").trim();
               const isDone = item.colorId === "8"; // 8 = Grafite/Cinza
               const endDt = item.end?.dateTime ? new Date(item.end.dateTime) : null;

               if (isDone) {
                 concluidos.add(syncId);
                 // Opcional: Se quiséssemos a 'Regra de União' perfeitamente integrada ao backend,
                 // faríamos um POST /api/planner/mark-done aqui para atualizar o Banco de Dados (App).
               } else if (endDt) {
                 paraDeletar.add(item.id);
               }
            }

            // 2. Monta a lista linear de todas as matérias que AINDA NÃO FORAM FEITAS
            const aulasPendentes: { title: string, description: string, duration: number, area: string }[] = [];
            const origin = typeof window !== "undefined" ? window.location.origin : "";
            
            for (const week of plan) {
               for (const topic of week.topics) {
                  const syncId = `${topic.subtema} (${topic.area})`;
                  if (concluidos.has(syncId)) continue; // Já fez, pula!

                  const durationMinutes = Math.max(30, Math.round(topic.estimated_hours * 60));
                  const desc = `📚 Carga: ${topic.estimated_hours}h (Teoria: ${topic.estimated_theory_hours}h + Questões: ${topic.estimated_practice_hours}h)
Semana ${week.week} • ${topic.area}${origin ? `

🔗 Questões: ${origin}/estudar?subtema=${encodeURIComponent(topic.subtema)}&limit=25` : ""}`;
                  
                  aulasPendentes.push({
                     title: `[MedQuest] 📖 ${syncId}`,
                     description: desc,
                     duration: durationMinutes,
                     area: topic.area
                  });
               }
            }

            // 3. Aplica a Ordem de Prioridade (O Efeito Cascata)
            // Identifica qual o rodízio atual (Hardcoded Turma J para exemplo rápido)
            const rodizios = [
              { start: new Date("2026-09-01"), end: new Date("2026-11-26"), area: "Ginecologia e Obstetrícia" },
              { start: new Date("2026-11-27"), end: new Date("2027-01-25"), area: "Preventiva" },
              { start: new Date("2027-01-26"), end: new Date("2027-02-22"), area: "Cirurgia" },
            ];
            
            let areaAtual = "";
            for (const r of rodizios) {
               if (now >= r.start && now <= r.end) areaAtual = r.area;
            }

            if (areaAtual) {
               aulasPendentes.sort((a, b) => {
                  if (a.area === areaAtual && b.area !== areaAtual) return -1;
                  if (b.area === areaAtual && a.area !== areaAtual) return 1;
                  return 0; // Mantém a ordem sequencial original do currículo
               });
            }

            // 4. Deleta todos os azuis (para dar lugar ao reagendamento limpo)
            let delCount = 0;
            for (const evId of Array.from(paraDeletar)) {
               delCount++;
               onProgress?.({ current: delCount, total: paraDeletar.size, status: `Limpando blocos atrasados/futuros...` });
               await fetch(
                  `https://www.googleapis.com/calendar/v3/calendars/${encodeURIComponent(targetCalId)}/events/${encodeURIComponent(evId)}`,
                  { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } }
               ).catch(e => console.log(e));
            }

            // 5. Aloca os novos horários (O Efeito Cascata em si)
            const studyDaysCount = Math.max(1, Math.min(7, daysPerWeek));
            let currentPointerDate = new Date();
            currentPointerDate.setHours(8, 0, 0, 0);
            
            const totalToInsert = aulasPendentes.length;
            for (let i = 0; i < totalToInsert; i++) {
               const aula = aulasPendentes[i];
               
               // Lógica simplificada de alocação de dias de estudo (Pula fins de semana se daysPerWeek=5 etc)
               const endPointerDate = new Date(currentPointerDate.getTime() + aula.duration * 60000);

               onProgress?.({
                 current: i + 1,
                 total: totalToInsert,
                 status: `Criando evento da Cascata: ${aula.title}...`
               });

               await fetch(
                  `https://www.googleapis.com/calendar/v3/calendars/${encodeURIComponent(targetCalId)}/events`,
                  {
                     method: "POST",
                     headers: {
                       Authorization: `Bearer ${accessToken}`,
                       "Content-Type": "application/json",
                     },
                     body: JSON.stringify({
                       summary: aula.title,
                       description: aula.description,
                       colorId: "9", // Azul
                       start: { dateTime: currentPointerDate.toISOString(), timeZone: "America/Sao_Paulo" },
                       end: { dateTime: endPointerDate.toISOString(), timeZone: "America/Sao_Paulo" }
                     }),
                  }
               );
               
               // Avança o dia para o próximo slot (Exemplo simplificado de 1 aula por dia)
               currentPointerDate.setDate(currentPointerDate.getDate() + 1);
            }

            resolve({ success: true, calendarId: targetCalId });
          } catch (err) {
            reject(err);
          }
        },
      });

      tokenClient.requestAccessToken();
    } catch (err) {
      reject(err);
    }
  });
}

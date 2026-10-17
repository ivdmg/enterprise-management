import { useState, useEffect } from 'react';
import {
  Building2,
  Send,
  Bell,
  CheckCircle2,
  Clock,
  Shield,
  Save,
} from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { Badge } from '@/components/Badge';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/api/client';
import type { TelegramSettings } from '@/types';

export function SettingsTab() {
  const { user } = useAuth();
  const [settings, setSettings] = useState<TelegramSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    apiClient
      .getTelegramSettings()
      .then((data) => {
        if (mounted) {
          setSettings(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to load telegram settings', err);
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 4000);
  };

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      await apiClient.updateTelegramSettings(settings);
      showToast('Настройки успешно сохранены');
    } catch {
      showToast('Ошибка при сохранении настроек');
    } finally {
      setSaving(false);
    }
  };

  const handleTestSend = async () => {
    setTesting(true);
    try {
      const res = await apiClient.testTelegramSend();
      showToast(res.message);
    } catch {
      showToast('Не удалось отправить тестовое сообщение');
    } finally {
      setTesting(false);
    }
  };

  if (loading || !settings) {
    return (
      <div className="py-12 flex justify-center">
        <div className="h-6 w-6 border-2 border-[var(--text-main)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 shadow-xl text-sm font-semibold transition-all">
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-[var(--text-main)] tracking-tight">
          Настройки системы
        </h1>
        <p className="text-xs text-[var(--text-sub)] mt-1">
          Управление профилем компании, интеграциями оповещений и правилами рисков
        </p>
      </div>

      {/* Company & Profile Info */}
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-5 pb-4 border-b border-[var(--card-border)]">
          <div className="p-2.5 rounded-xl bg-[var(--card-subtle)] text-[var(--text-main)]">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[var(--text-main)]">
              Данные организации
            </h2>
            <p className="text-xs text-[var(--text-sub)]">
              Основные реквизиты вашей компании в Smart Enterprise Hub
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1">
              Организация
            </label>
            <div className="px-3.5 py-2.5 rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)] font-medium text-[var(--text-main)]">
              ООО «ГлавСтройИнжиниринг»
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1">
              ИНН организации
            </label>
            <div className="px-3.5 py-2.5 rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)] font-mono text-[var(--text-main)]">
              7701987654
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1">
              Администратор
            </label>
            <div className="px-3.5 py-2.5 rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)] text-[var(--text-main)]">
              {user?.full_name || 'Иванов Иван Иванович'}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1">
              Электронная почта
            </label>
            <div className="px-3.5 py-2.5 rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)] text-[var(--text-main)]">
              {user?.email || 'director@glavstroy.ru'}
            </div>
          </div>
        </div>
      </Card>

      {/* Telegram Integration */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-5 pb-4 border-b border-[var(--card-border)]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-[var(--card-subtle)] text-[var(--text-main)]">
              <Send className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-[var(--text-main)]">
                  Интеграция с Telegram
                </h2>
                <Badge variant="success">Подключен</Badge>
              </div>
              <p className="text-xs text-[var(--text-sub)] mt-0.5">

                Бот @{settings.bot_username} отправляет утренний дайджест и критические алерты
              </p>
            </div>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={handleTestSend}
            isLoading={testing}
            id="test-telegram-btn"
          >
            Тестовое сообщение
          </Button>
        </div>

        {/* Telegram Options */}
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3.5 rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)]">
            <div className="flex items-center gap-3">
              <Clock className="h-5 w-5 text-[var(--text-muted)]" />
              <div>
                <p className="text-sm font-semibold text-[var(--text-main)]">
                  Ежедневный утренний дайджест
                </p>
                <p className="text-xs text-[var(--text-sub)]">
                  Краткая сводка рисков и финансового состояния в 08:30
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="time"
                value={settings.daily_digest_time}
                onChange={(e) =>
                  setSettings({ ...settings, daily_digest_time: e.target.value })
                }
                className="px-2.5 py-1 text-sm rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--text-main)]"
              />
              <input
                type="checkbox"
                checked={settings.daily_digest_enabled}
                onChange={(e) =>
                  setSettings({ ...settings, daily_digest_enabled: e.target.checked })
                }
                className="h-4 w-4 rounded accent-slate-900 dark:accent-slate-100 cursor-pointer"
              />
            </div>
          </div>

          <div className="flex items-center justify-between p-3.5 rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)]">
            <div className="flex items-center gap-3">
              <Bell className="h-5 w-5 text-[var(--text-muted)]" />
              <div>
                <p className="text-sm font-semibold text-[var(--text-main)]">
                  Мгновенные оповещения о критических срывах
                </p>
                <p className="text-xs text-[var(--text-sub)]">
                  Отправлять push в Telegram при выявлении критического риска
                </p>
              </div>
            </div>
            <input
              type="checkbox"
              checked={settings.alert_rules.notify_on_critical_instant}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  alert_rules: {
                    ...settings.alert_rules,
                    notify_on_critical_instant: e.target.checked,
                  },
                })
              }
              className="h-4 w-4 rounded accent-slate-900 dark:accent-slate-100 cursor-pointer"
            />
          </div>
        </div>
      </Card>

      {/* Risk Thresholds */}
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-5 pb-4 border-b border-[var(--card-border)]">
          <div className="p-2.5 rounded-xl bg-[var(--card-subtle)] text-[var(--text-main)]">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[var(--text-main)]">
              Пороги срабатывания алертов
            </h2>
            <p className="text-xs text-[var(--text-sub)]">
              Параметры детекции угроз и кассовых разрывов
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-[var(--text-main)] mb-1.5">
              Предупреждение о дедлайне (дней до срока)
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                max={30}
                value={settings.alert_rules.deadline_warning_days}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    alert_rules: {
                      ...settings.alert_rules,
                      deadline_warning_days: parseInt(e.target.value) || 1,
                    },
                  })
                }
                className="w-full px-3 py-2 text-xs rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--text-main)] focus:outline-none focus:ring-1 focus:ring-slate-900 dark:focus:ring-slate-100"
              />
              <span className="text-xs text-[var(--text-sub)] whitespace-nowrap">дней</span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--text-main)] mb-1.5">
              Горизонт прогнозирования кассового разрыва
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={7}
                max={60}
                value={settings.alert_rules.cash_gap_forecast_days}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    alert_rules: {
                      ...settings.alert_rules,
                      cash_gap_forecast_days: parseInt(e.target.value) || 7,
                    },
                  })
                }
                className="w-full px-3 py-2 text-xs rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--text-main)] focus:outline-none focus:ring-1 focus:ring-slate-900 dark:focus:ring-slate-100"
              />
              <span className="text-xs text-[var(--text-sub)] whitespace-nowrap">дней</span>
            </div>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3 pt-4 border-t border-[var(--card-border)]">
          <Button
            variant="primary"
            onClick={handleSave}
            isLoading={saving}
            icon={Save}
            id="save-settings-btn"
          >
            Сохранить настройки
          </Button>
        </div>
      </Card>

    </div>
  );
}

import { Modal } from '@/components/Modal';
import { useRole } from '@/context/RoleContext';
import { useToast } from '@/context/ToastContext';
import {
  type EnterpriseRoleDefinition,
} from '@/types/roles';
import {
  Crown,
  ShieldCheck,
  Briefcase,
  HardHat,
  Radio,
  Layers,
  Scale,
  ShoppingBag,
  Receipt,
  Check,
} from 'lucide-react';

interface RoleSwitcherModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRoleSelected?: (tabToNavigate?: string) => void;
}

function getRoleIcon(iconName: string) {
  const iconProps = { className: 'h-4 w-4 shrink-0' };
  switch (iconName) {
    case 'Crown':
      return <Crown {...iconProps} />;
    case 'ShieldCheck':
      return <ShieldCheck {...iconProps} />;
    case 'Briefcase':
      return <Briefcase {...iconProps} />;
    case 'HardHat':
      return <HardHat {...iconProps} />;
    case 'Radio':
      return <Radio {...iconProps} />;
    case 'Layers':
      return <Layers {...iconProps} />;
    case 'Scale':
      return <Scale {...iconProps} />;
    case 'ShoppingBag':
      return <ShoppingBag {...iconProps} />;
    case 'Receipt':
      return <Receipt {...iconProps} />;
    default:
      return <Briefcase {...iconProps} />;
  }
}

export function RoleSwitcherModal({ isOpen, onClose, onRoleSelected }: RoleSwitcherModalProps) {
  const { activeRole, setActiveRole, roles } = useRole();
  const { showToast } = useToast();

  const handleSelectRole = (roleDef: EnterpriseRoleDefinition) => {
    setActiveRole(roleDef.id);
    showToast(`Фокус интерфейса переключен: ${roleDef.name}`, 'info');
    onClose();
    if (onRoleSelected) {
      onRoleSelected(roleDef.primaryTab);
    }
  };

  // Group roles by department
  const departments = Array.from(new Set(roles.map((r) => r.department)));

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Выбор активной роли сотрудника"
      size="lg"
    >
      <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Выберите роль для быстрой адаптации рабочих вкладок, алертов и оперативных задач компании.
        </p>

        {departments.map((dept) => {
          const deptRoles = roles.filter((r) => r.department === dept);
          return (
            <div key={dept} className="space-y-2">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                {dept}
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {deptRoles.map((role) => {
                  const isSelected = role.id === activeRole;
                  return (
                    <button
                      key={role.id}
                      type="button"
                      onClick={() => handleSelectRole(role)}
                      className={`min-h-[52px] w-full text-left p-3 rounded-lg border transition-all flex items-start gap-3 ${
                        isSelected
                          ? 'border-indigo-600 bg-indigo-50/50 dark:bg-indigo-950/30 text-indigo-900 dark:text-indigo-200 shadow-xs'
                          : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800/60 text-slate-800 dark:text-slate-200'
                      }`}
                    >
                      <div
                        className={`p-2 rounded-md shrink-0 mt-0.5 ${
                          isSelected
                            ? 'bg-indigo-600 text-white'
                            : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                        }`}
                      >
                        {getRoleIcon(role.iconName)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <p className="text-sm font-semibold truncate">{role.shortName}</p>
                          {isSelected && (
                            <Check className="h-4 w-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
                          )}
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 mt-0.5">
                          {role.description}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </Modal>
  );
}

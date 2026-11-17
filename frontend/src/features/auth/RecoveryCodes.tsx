export function RecoveryCodes({ codes, onContinue }: { codes: readonly string[]; onContinue: () => void }) {
  return (
    <main className="workspace-loading auth-page">
      <section className="auth-access">
        <h1>Коды восстановления</h1>
        <p>Сохраните коды в безопасном месте. Каждый код можно использовать один раз. После выхода с этого экрана коды больше не будут показаны.</p>
        <ul className="grid grid-cols-2 gap-2 py-4 font-mono">
          {codes.map(code => <li key={code}>{code}</li>)}
        </ul>
        <button className="auth-submit" onClick={onContinue}>Коды сохранены</button>
      </section>
    </main>
  );
}

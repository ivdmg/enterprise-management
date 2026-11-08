export function Pagination({ page, total, pageSize, onPage }: {
  page: number; total: number; pageSize: number; onPage: (page: number) => void;
}) {
  const pages = Math.ceil(total / pageSize);
  if (pages < 2) return null;

  const visible = pages <= 10
    ? Array.from({ length: pages }, (_, index) => index)
    : [...new Set([0, 1, page - 2, page - 1, page, page + 1, page + 2, pages - 2, pages - 1])]
      .filter(index => index >= 0 && index < pages)
      .sort((a, b) => a - b);

  return <nav className="workspace-pagination" aria-label="Страницы списка">
    {visible.map((index, position) => {
      const previous = visible[position - 1];
      const button = (value: number) => <button type="button" aria-label={'Страница ' + (value + 1)}
        aria-current={value === page ? 'page' : undefined} onClick={() => onPage(value)}>{value + 1}</button>;
      return <span className="workspace-pagination-group" key={index}>
        {index - previous === 2 ? button(previous + 1) :
          index - previous > 2 && <span className="workspace-pagination-gap" aria-hidden="true">…</span>}
        {button(index)}
      </span>;
    })}
  </nav>;
}

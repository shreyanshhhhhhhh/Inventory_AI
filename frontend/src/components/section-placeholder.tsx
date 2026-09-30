export function SectionPlaceholder({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <section className="space-y-2">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {description ? (
        <p className="max-w-xl text-sm text-muted-foreground">{description}</p>
      ) : null}
    </section>
  );
}

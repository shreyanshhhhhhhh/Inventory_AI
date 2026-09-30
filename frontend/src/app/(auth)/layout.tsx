export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-full flex-1 items-center justify-center bg-muted/30 p-6">
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}

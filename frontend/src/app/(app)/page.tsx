import { ApiStatus } from "@/components/api-status";
import { SectionPlaceholder } from "@/components/section-placeholder";

export default function HomePage() {
  return (
    <div className="space-y-4">
      <SectionPlaceholder
        title="Home"
        description="On-hand units, inventory value, low stock, and open purchase orders will show here."
      />
      <ApiStatus />
    </div>
  );
}

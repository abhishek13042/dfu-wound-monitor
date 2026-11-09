import { MedicalNotice } from "@/components/MedicalNotice";
import { Rail } from "@/components/Rail";
import { getReadiness } from "@/lib/api";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const readiness = await getReadiness();
  return (
    <div className="min-[900px]:flex">
      <Rail readiness={readiness} />
      <div className="min-w-0 flex-1">
        <MedicalNotice />
        <main className="mx-auto max-w-[1180px] px-4 pt-6 pb-16 sm:px-6">{children}</main>
      </div>
    </div>
  );
}

import type { Metadata } from "next";

import { NewCaseForm } from "@/components/NewCaseForm";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "New case" };

export default function NewCasePage() {
  return (
    <>
      <PageHeader title="New case">A case groups the examinations of one wound over time.</PageHeader>
      <NewCaseForm />
    </>
  );
}

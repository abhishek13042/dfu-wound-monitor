"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";

interface Props {
  action: string;
  title: string;
  body: string;
  word: string;
  redirect: string;
}

// Deletion cannot be undone, so it gets protected focus and a typed confirmation.
export function ConfirmDialog({ action, title, body, word, redirect }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [typed, setTyped] = useState("");
  const router = useRouter();
  return (
    <>
      <Button variant="outline" className="border-failure text-failure hover:bg-failure-wash" onClick={() => dialog.current?.showModal()}>
        {action}
      </Button>
      <dialog
        ref={dialog}
        aria-labelledby="confirm-title"
        onClose={() => setTyped("")}
        className="panel m-auto w-[calc(100%-32px)] max-w-md p-5 shadow-menu backdrop:bg-aubergine/70"
      >
        <h2 id="confirm-title" className="text-lg">{title}</h2>
        <p className="mt-2 text-sm text-ink-2">{body}</p>
        <label className="mt-4 block text-sm font-medium">
          Type <span className="value">{word}</span> to confirm
          <input value={typed} onChange={(event) => setTyped(event.target.value)} autoComplete="off" className="field mt-1" />
        </label>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => dialog.current?.close()}>Keep it</Button>
          <Button variant="destructive" disabled={typed !== word} onClick={() => router.push(redirect)}>{action}</Button>
        </div>
      </dialog>
    </>
  );
}

"use client";

import dynamic from "next/dynamic";

const VeritasApp = dynamic(() => import("@/components/VeritasApp"), {
  ssr: false,
  loading: () => null,
});

export default function Page() {
  return <VeritasApp />;
}

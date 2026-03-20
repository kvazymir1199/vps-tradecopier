"use client";
import { useState } from "react";
import { TerminalsTable } from "@/components/terminals-table";
import { LinksTable } from "@/components/links-table";
import { MappingsPanel } from "@/components/mappings-panel";
import { Toaster } from "@/components/ui/sonner";

export default function Home() {
  const [selectedLinkId, setSelectedLinkId] = useState<number | null>(null);

  return (
    <main className="container mx-auto py-8 space-y-8 px-4">
      <TerminalsTable />
      <LinksTable onSelectLink={setSelectedLinkId} />
      {selectedLinkId && (
        <MappingsPanel
          linkId={selectedLinkId}
          open={true}
          onOpenChange={(open) => { if (!open) setSelectedLinkId(null); }}
        />
      )}
      <Toaster />
    </main>
  );
}

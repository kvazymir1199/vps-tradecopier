"use client";

import { useState } from "react";
import { LinksTable } from "@/components/links-table";
import { MappingsPanel } from "@/components/mappings-panel";

export default function LinksPage() {
  const [selectedLinkId, setSelectedLinkId] = useState<number | null>(null);

  return (
    <>
      <LinksTable onSelectLink={setSelectedLinkId} />
      {selectedLinkId && (
        <MappingsPanel
          linkId={selectedLinkId}
          open={true}
          onOpenChange={(open) => {
            if (!open) setSelectedLinkId(null);
          }}
        />
      )}
    </>
  );
}

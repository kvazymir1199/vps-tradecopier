"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Link } from "@/types";
import { useLinks } from "@/hooks/use-links";
import { useTerminals } from "@/hooks/use-terminals";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { AddLinkDialog } from "@/components/add-link-dialog";
import { EditLinkDialog } from "@/components/edit-link-dialog";

interface LinksTableProps {
  onSelectLink: (linkId: number) => void;
}

export function LinksTable({ onSelectLink }: LinksTableProps) {
  const { links, loading, createLink, updateLink, toggleLink, deleteLink } =
    useLinks();
  const { terminals } = useTerminals();

  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingLink, setEditingLink] = useState<Link | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const handleCreate = async (data: {
    master_id: string;
    slave_id: string;
    lot_mode: string;
    lot_value: number;
    symbol_suffix: string;
  }) => {
    try {
      await createLink(data);
      toast.success("Link created successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create link");
      throw err;
    }
  };

  const handleEdit = async (
    id: number,
    data: { lot_mode: string; lot_value: number; symbol_suffix: string }
  ) => {
    try {
      await updateLink(id, data);
      toast.success("Link updated successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update link");
      throw err;
    }
  };

  const handleToggle = async (id: number) => {
    try {
      await toggleLink(id);
      toast.success("Link toggled");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to toggle link");
    }
  };

  const handleDelete = async () => {
    if (deleteId === null) return;
    try {
      await deleteLink(deleteId);
      toast.success("Link deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete link");
    } finally {
      setDeleteId(null);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">Links</h2>
          {loading && (
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent opacity-50" />
          )}
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          + Add Link
        </Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Master</TableHead>
            <TableHead>Slave</TableHead>
            <TableHead>Lot Mode</TableHead>
            <TableHead>Lot Value</TableHead>
            <TableHead>Suffix</TableHead>
            <TableHead>Enabled</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {links.length === 0 && !loading ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-muted-foreground">
                No links configured
              </TableCell>
            </TableRow>
          ) : (
            links.map((link) => (
              <TableRow
                key={link.id}
                className="cursor-pointer"
                onClick={() => onSelectLink(link.id)}
              >
                <TableCell className="font-mono text-xs">
                  {link.master_id}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {link.slave_id}
                </TableCell>
                <TableCell className="capitalize">{link.lot_mode}</TableCell>
                <TableCell>{link.lot_value}</TableCell>
                <TableCell>{link.symbol_suffix || "-"}</TableCell>
                <TableCell>
                  <Switch
                    checked={link.enabled === 1}
                    onCheckedChange={() => handleToggle(link.id)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingLink(link);
                        setEditOpen(true);
                      }}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="destructive"
                      size="xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteId(link.id);
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      <AddLinkDialog
        terminals={terminals}
        onSubmit={handleCreate}
        open={addOpen}
        onOpenChange={setAddOpen}
      />

      <EditLinkDialog
        link={editingLink}
        onSubmit={handleEdit}
        open={editOpen}
        onOpenChange={setEditOpen}
      />

      <AlertDialog
        open={deleteId !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteId(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Link</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this link? This action cannot be
              undone. All associated mappings will also be removed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleDelete}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

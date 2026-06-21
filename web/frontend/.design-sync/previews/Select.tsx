import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "frontend";

export function Open() {
  return (
    <Select defaultValue="multiplier" defaultOpen>
      <SelectTrigger style={{ width: 260 }}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="multiplier">Multiplier</SelectItem>
        <SelectItem value="fixed">Fixed</SelectItem>
      </SelectContent>
    </Select>
  );
}

export function Closed() {
  return (
    <Select defaultValue="MT5-Master-01">
      <SelectTrigger style={{ width: 260 }}>
        <SelectValue placeholder="Select master terminal" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="MT5-Master-01">MT5-Master-01</SelectItem>
        <SelectItem value="MT5-Master-02">MT5-Master-02</SelectItem>
      </SelectContent>
    </Select>
  );
}

const $ = {
  text: undefined,
};

export function renderDemo() {
  return ($.text || "").trim();
}

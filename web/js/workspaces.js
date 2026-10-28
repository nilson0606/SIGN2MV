// Loads the workspace modules (sing & record, MV, AI cover) that exist so far.
// Each module registers its page with registerPage() from app-state.js.
const modules = [];
await Promise.allSettled(modules.map((m) => import(m)));

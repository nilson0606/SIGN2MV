// Loads the workspace modules (sing & record, MV, AI cover) that exist so far.
// Each module registers its page with registerPage() from app-state.js.
const modules = ['./sing.js', './mv.js', './cover.js'];
await Promise.allSettled(modules.map((m) => import(m)));

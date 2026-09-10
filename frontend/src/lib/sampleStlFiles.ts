// Bundled sample STL files (frontend/public/sample_stl/) — served as plain
// static assets by whatever's hosting the frontend (GitHub Pages, the local
// Vite dev server, etc.), no backend involved in listing or fetching them.
//
// This exists because the "pick an existing file" dropdown (api.ts's
// listCadUploads/fetchCadUpload) depends on a reachable backend, which the
// public GitHub Pages demo doesn't have — without these, that dropdown is
// always empty there. Picking a bundled sample still needs a backend for
// the actual "Generate path" step (that's real STL-parsing + geometry work,
// api.generatePath), same as any other selected file; this only fixes
// *seeing and selecting* a file to work with.
export interface SampleStlFile {
  name: string;
  url: string;
}

export const SAMPLE_STL_FILES: SampleStlFile[] = [
  { name: "3DBenchy.stl", url: `${import.meta.env.BASE_URL}sample_stl/3DBenchy.stl` },
  { name: "test_box.stl", url: `${import.meta.env.BASE_URL}sample_stl/test_box.stl` },
];

export async function fetchSampleStlFile(sample: SampleStlFile): Promise<File> {
  const res = await fetch(sample.url);
  if (!res.ok) throw new Error(`Could not load bundled sample ${sample.name} (${res.status})`);
  const blob = await res.blob();
  return new File([blob], sample.name, { type: "application/sla" });
}

export type StorySource = { id: string; title: string; url: string; accessed_on: string }
export type StoryFact = { text: string; source_ids: string[]; status: 'sourced' | 'unverified' }
export type StoryImage = { url: string; caption: string; credit: string; source_url: string }
export type TimelineEvent = StoryFact & { id: string; title: string; period: string; year_start: number; year_end: number | null; image: StoryImage | null }
export type CameraView = 'front' | 'top' | 'park' | 'cinematic'
export type ArchitectureDetail = StoryFact & { title: string; view: CameraView | null }
export type LandmarkStory = {
  overview: StoryFact; image: StoryImage | null; timeline: TimelineEvent[]; architecture: ArchitectureDetail[]
  visit: { address: StoryFact; duration: StoryFact; hours: StoryFact; admission: StoryFact; notes: StoryFact; checked_on: string | null }
  sources: StorySource[]
}
export type StoryResponse = { model_id: string; display_name: string; content: LandmarkStory | null; published_at: string | null }

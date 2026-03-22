"use client"

import { useMemo, useState } from "react"

const hookTemplates = {
  creator: [
    "The {topic} mistake that kills short-form retention in 3 seconds",
    "I changed one thing about {topic} and the clips got instantly sharper",
    "Nobody tells creators this about turning {topic} into shorts",
    "If your {topic} clips feel flat, start here",
  ],
  podcast: [
    "This {topic} take is why the full episode is getting clipped",
    "The strongest 20 seconds from our {topic} conversation",
    "You can hear the room change when {topic} comes up",
    "The {topic} moment that deserved its own clip",
  ],
  agency: [
    "How we turn one {topic} asset into a week of short-form content",
    "The client-safe way to repurpose {topic} without generic output",
    "Why our {topic} workflow still keeps an editor in the loop",
    "The repeatable {topic} playbook for short-form ops",
  ],
} as const

type Audience = keyof typeof hookTemplates

export function HookIdeaGenerator() {
  const [topic, setTopic] = useState("AI clip detection")
  const [audience, setAudience] = useState<Audience>("creator")

  const ideas = useMemo(() => {
    return hookTemplates[audience].map((template) =>
      template.replace("{topic}", topic.trim() || "your topic"),
    )
  }, [audience, topic])

  return (
    <div className="section-card">
      <div className="grid-2">
        <label>
          <span className="eyebrow">Topic</span>
          <input
            className="field"
            onChange={(event) => setTopic(event.target.value)}
            placeholder="Enter a topic"
            value={topic}
          />
        </label>
        <label>
          <span className="eyebrow">Audience</span>
          <select
            className="field"
            onChange={(event) => setAudience(event.target.value as Audience)}
            value={audience}
          >
            <option value="creator">Creator</option>
            <option value="podcast">Podcast</option>
            <option value="agency">Agency</option>
          </select>
        </label>
      </div>
      <div className="grid-2" style={{ marginTop: "1rem" }}>
        {ideas.map((idea) => (
          <article className="section-card" key={idea}>
            <p>{idea}</p>
          </article>
        ))}
      </div>
    </div>
  )
}

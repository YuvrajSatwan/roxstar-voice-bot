import React from 'react';
import type { UserDiscoveryProfile } from '../hooks/useStsRoom';
import { UserCheck } from 'lucide-react';

interface DiscoveryProfileBadgeProps {
  profile: UserDiscoveryProfile | null;
  discoveredTopics: string[];
}

export const DiscoveryProfileBadge: React.FC<DiscoveryProfileBadgeProps> = ({
  profile,
  discoveredTopics,
}) => {
  if (!profile || discoveredTopics.length === 0) return null;

  return (
    <div className="discovery-badges-wrap" title="Discovered during conversation">
      <div className="discovery-badges-header">
        <UserCheck size={12} />
        <span>Memory & Profile</span>
      </div>
      <div className="discovery-badges-list">
        {profile.name && <span className="discovery-chip">Name: {profile.name}</span>}
        {profile.location && <span className="discovery-chip">📍 {profile.location}</span>}
        {profile.occupation && <span className="discovery-chip">💼 {profile.occupation}</span>}
        {profile.music_taste.map((t) => (
          <span key={t} className="discovery-chip">🎵 {t}</span>
        ))}
        {profile.hobbies.map((h) => (
          <span key={h} className="discovery-chip">✨ {h}</span>
        ))}
      </div>
    </div>
  );
};


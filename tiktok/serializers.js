'use strict';

function extractHashtags(caption) {
  const matches = caption.match(/#[a-z0-9_]+/gi) || [];
  return Array.from(new Set(matches.map((t) => t.slice(1).toLowerCase())));
}

function followerCount(state, userId) {
  const user = state.users.find((u) => u.id === userId);
  const real = state.follows.filter((f) => f.followingId === userId && !f.isSeed).length;
  const seed = state.follows.filter((f) => f.followingId === userId && f.isSeed).length;
  return (user ? user.seedFollowers : 0) + real + seed;
}

function followingCount(state, userId) {
  const user = state.users.find((u) => u.id === userId);
  const rows = state.follows.filter((f) => f.followerId === userId).length;
  return (user ? user.seedFollowing || 0 : 0) + rows;
}

function isFollowing(state, viewerId, targetId) {
  if (!viewerId) return false;
  return state.follows.some((f) => f.followerId === viewerId && f.followingId === targetId);
}

function videoLikeCount(state, videoId) {
  const video = state.videos.find((v) => v.id === videoId);
  const real = state.likes.filter((l) => l.videoId === videoId).length;
  return (video ? video.seedLikes : 0) + real;
}

function videoCommentCount(state, videoId) {
  return state.comments.filter((c) => c.videoId === videoId).length;
}

function commentLikeCount(state, commentId) {
  const c = state.comments.find((x) => x.id === commentId);
  const real = state.likes.filter((l) => l.commentId === commentId).length;
  return (c ? c.seedLikes || 0 : 0) + real;
}

function totalLikesForUser(state, userId) {
  const vids = state.videos.filter((v) => v.authorId === userId);
  return vids.reduce((sum, v) => sum + videoLikeCount(state, v.id), 0);
}

function publicUser(state, user, viewerId) {
  if (!user) return null;
  return {
    id: user.id,
    username: user.username,
    displayName: user.displayName,
    bio: user.bio || '',
    avatarSeed: user.avatarSeed,
    verified: !!user.verified,
    followers: followerCount(state, user.id),
    following: followingCount(state, user.id),
    likes: totalLikesForUser(state, user.id),
    videoCount: state.videos.filter((v) => v.authorId === user.id).length,
    isFollowing: isFollowing(state, viewerId, user.id),
    isSelf: viewerId === user.id,
    createdAt: user.createdAt,
  };
}

function publicVideo(state, video, viewerId) {
  const author = state.users.find((u) => u.id === video.authorId);
  return {
    id: video.id,
    caption: video.caption,
    hashtags: extractHashtags(video.caption),
    type: video.type,
    style: video.style || null,
    visualSeed: video.visualSeed || 0,
    url: video.url || null,
    mimetype: video.mimetype || null,
    soundId: video.soundId || null,
    soundName: video.soundName,
    createdAt: video.createdAt,
    stats: {
      likes: videoLikeCount(state, video.id),
      comments: videoCommentCount(state, video.id),
      shares: video.shares || 0,
      views: video.views || 0,
    },
    isLiked: viewerId ? state.likes.some((l) => l.videoId === video.id && l.userId === viewerId) : false,
    author: author ? {
      id: author.id,
      username: author.username,
      displayName: author.displayName,
      avatarSeed: author.avatarSeed,
      verified: !!author.verified,
      isFollowing: isFollowing(state, viewerId, author.id),
      isSelf: viewerId === author.id,
    } : null,
  };
}

function publicComment(state, comment, viewerId) {
  const author = state.users.find((u) => u.id === comment.authorId);
  return {
    id: comment.id,
    videoId: comment.videoId,
    parentId: comment.parentId || null,
    text: comment.text,
    createdAt: comment.createdAt,
    likes: commentLikeCount(state, comment.id),
    isLiked: viewerId ? state.likes.some((l) => l.commentId === comment.id && l.userId === viewerId) : false,
    isOwn: viewerId === comment.authorId,
    author: author ? {
      id: author.id,
      username: author.username,
      displayName: author.displayName,
      avatarSeed: author.avatarSeed,
      verified: !!author.verified,
    } : null,
  };
}

function publicSound(state, sound) {
  const uses = state.videos.filter((v) => v.soundId === sound.id).length;
  return {
    id: sound.id,
    name: sound.name,
    uses: (sound.seedUses || 0) + uses,
  };
}

module.exports = {
  extractHashtags,
  followerCount,
  followingCount,
  isFollowing,
  videoLikeCount,
  videoCommentCount,
  commentLikeCount,
  totalLikesForUser,
  publicUser,
  publicVideo,
  publicComment,
  publicSound,
};

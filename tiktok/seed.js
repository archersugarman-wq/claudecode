'use strict';
const { hashPassword } = require('./auth');

// Deterministic PRNG (mulberry32) so re-seeding (if the db is ever wiped)
// always produces the same demo content.
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rand = mulberry32(20260903);
const pick = (arr) => arr[Math.floor(rand() * arr.length)];
const int = (min, max) => Math.floor(rand() * (max - min + 1)) + min;

const USERS = [
  { username: 'chefmarco', displayName: 'Marco Rossi', bio: 'Chef 🍝 Sharing 60-second recipes from my nonna\'s kitchen', avatarSeed: 1, verified: true, style: 'plasma', theme: 'cooking' },
  { username: 'luna.codes', displayName: 'Luna Chen', bio: 'Senior SWE by day, coding tips by night 💻 she/her', avatarSeed: 2, verified: true, style: 'matrix', theme: 'coding' },
  { username: 'wanderwithava', displayName: 'Ava Torres', bio: 'Currently: somewhere with bad wifi ✈️ 38 countries', avatarSeed: 3, verified: false, style: 'aurora', theme: 'travel' },
  { username: 'fitwithjay', displayName: 'Jay Okafor', bio: 'Certified trainer 💪 No excuses, just reps', avatarSeed: 4, verified: true, style: 'waves', theme: 'fitness' },
  { username: 'sketch.sara', displayName: 'Sara Kim', bio: 'Digital artist ✏️ commissions open (link below)', avatarSeed: 5, verified: false, style: 'particles', theme: 'art' },
  { username: 'thepixelpup', displayName: 'Biscuit 🐾', bio: 'corgi. professional zoomie enjoyer. good boy certified', avatarSeed: 6, verified: false, style: 'bounce', theme: 'pets' },
  { username: 'beatsbyremy', displayName: 'Remy Fontaine', bio: 'producer 🎧 new beat every friday', avatarSeed: 7, verified: false, style: 'bars', theme: 'music' },
  { username: 'comedy.carl', displayName: 'Carl Jennings', bio: 'just a guy making bits 🎭 booking: link in bio', avatarSeed: 8, verified: true, style: 'confetti', theme: 'comedy' },
  { username: 'diydana', displayName: 'Dana Whitfield', bio: 'turning thrift finds into furniture 🔨🏠', avatarSeed: 9, verified: false, style: 'starfield', theme: 'diy' },
  { username: 'studywithmei', displayName: 'Mei Nakamura', bio: 'med student 📚 productivity + study-with-me videos', avatarSeed: 10, verified: false, style: 'tunnel', theme: 'study' },
  { username: 'gamer.gio', displayName: 'Giovanni Reyes', bio: 'speedrunner 🎮 clipping my best (and worst) plays', avatarSeed: 11, verified: false, style: 'tunnel', theme: 'gaming' },
  { username: 'natureby.noah', displayName: 'Noah Bennett', bio: 'trail runner + amateur botanist 🌲 PNW based', avatarSeed: 12, verified: false, style: 'aurora', theme: 'nature' },
  { username: 'fashionfaye', displayName: 'Faye Whitmore', bio: 'thrift flips + styling on a budget 👗', avatarSeed: 13, verified: true, style: 'particles', theme: 'fashion' },
  { username: 'dance.crew.kx', displayName: 'KX Dance Crew', bio: '5 dancers, 1 studio, 0 chill 💃🕺', avatarSeed: 14, verified: true, style: 'confetti', theme: 'dance' },
];

const THEME_CONTENT = {
  cooking: {
    captions: [
      '15-minute garlic butter pasta that tastes like a restaurant made it 🍝',
      'the secret to crispy chicken skin nobody tells you about',
      'my nonna would disown me if she saw this shortcut... but it works',
      'one-pot risotto so you only wash one pan (you\'re welcome)',
      'this $4 dinner slaps harder than takeout, fight me',
      'brown butter changes EVERYTHING. here\'s how not to burn it',
    ],
    tags: ['cooking', 'recipe', 'foodtok', 'easyrecipe', 'italianfood', 'homecooking'],
  },
  coding: {
    captions: [
      'the one VS Code shortcut that saved me 4 hours a week',
      'senior devs don\'t write more code, they delete more code',
      'explaining recursion using literally just this one gif',
      'you\'re probably using useEffect wrong, here\'s why',
      'I refactored 400 lines into 12. here\'s the diff',
      'the interview question that broke me (and how I\'d answer it now)',
    ],
    tags: ['coding', 'softwareengineer', 'webdev', 'programming', 'techtok', 'javascript'],
  },
  travel: {
    captions: [
      'POV: you booked a one-way ticket and figured out the rest later',
      'the cheapest way to island-hop that nobody talks about',
      'things I wish I knew before backpacking solo at 22',
      'this hostel had a rooftop pool for $9/night, I\'m never leaving',
      'packing my whole life into one 40L bag, ask me anything',
      'the sunset that made me delete my return flight',
    ],
    tags: ['travel', 'backpacking', 'solotravel', 'wanderlust', 'traveltok', 'digitalnomad'],
  },
  fitness: {
    captions: [
      '3 exercises that fixed my desk-job posture in a month',
      'you don\'t need a gym, you need 12 minutes and a wall',
      'progressive overload explained in under 30 seconds',
      'the warmup routine every runner is skipping (and shouldn\'t)',
      'day 1 vs day 90 of actually following a program',
      'why your squat form is probably wrong (and the fix)',
    ],
    tags: ['fitness', 'gymtok', 'workout', 'homeworkout', 'strengthtraining', 'fitnessjourney'],
  },
  art: {
    captions: [
      'painting a portrait using only 3 brushes, timelapse',
      'the blending technique that changed my digital art forever',
      'turning a client\'s worst photo into their favorite piece',
      'sketching strangers on the train, ep. 14',
      'color theory in 45 seconds because I know you won\'t read the book',
      'redrawing my art from 2019 vs now, the growth is wild',
    ],
    tags: ['art', 'digitalart', 'artistsoftiktok', 'drawing', 'illustration', 'sketch'],
  },
  pets: {
    charOverride: true,
    captions: [
      'me: "stay." also me, 0.3 seconds later:',
      'the zoomies hit different at 6am, sorry neighbors',
      'trying a new treat puzzle, my success rate: questionable',
      'reacting to the vacuum cleaner like it personally wronged me',
      'protecting the house from a very threatening leaf',
      'day 847 of asking for a second breakfast',
    ],
    tags: ['dogsoftiktok', 'corgi', 'dogtok', 'goodboy', 'petsoftiktok', 'zoomies'],
  },
  music: {
    captions: [
      'turning a voice memo into a full beat in 60 seconds',
      'this chord progression is illegal it\'s so good',
      'sampling my coffee maker for a hi-hat, don\'t judge me',
      'new beat dropping friday, here\'s a preview 👀',
      'the bassline that took me 3 hours and 2 energy drinks',
      'mixing vocals so they don\'t sound like a bathroom recording',
    ],
    tags: ['musicproducer', 'beats', 'producertok', 'newmusic', 'studiosession', 'hiphopbeats'],
  },
  comedy: {
    captions: [
      'when the waiter asks "how is everything" mid-bite',
      'group projects, a documentary',
      'me pretending I understood the meeting agenda',
      'explaining my search history to IT support',
      'when you say "you too" after the movie ticket guy says "enjoy the show"',
      'my phone at 1% vs my will to keep scrolling',
    ],
    tags: ['comedy', 'funny', 'skit', 'relatable', 'comedytiktok', 'fyp'],
  },
  diy: {
    captions: [
      '$15 thrift dresser to built-in-looking cabinet, no tools required',
      'the sanding mistake that ruins most beginner furniture flips',
      'turning pallet wood into a headboard nobody believes is free',
      'painting cabinets without the streaky brush marks, finally',
      'this $3 hardware swap made the whole piece look expensive',
      'before/after: the ugliest chair I\'ve ever saved',
    ],
    tags: ['diy', 'furnitureflip', 'thrifted', 'homedecor', 'upcycle', 'diyhomedecor'],
  },
  study: {
    captions: [
      'study with me: 50 min pomodoro, cafe ambience, no talking',
      'the note-taking method that finally stuck for anatomy',
      'how I memorize 200 flashcards in a day (it\'s spaced repetition)',
      'my exact desk setup for finals week, fully unplugged',
      'active recall vs rereading, the difference is not subtle',
      '3am library session because the exam doesn\'t care about my sleep schedule',
    ],
    tags: ['studytok', 'studywithme', 'medstudent', 'productivity', 'studymotivation', 'college'],
  },
  gaming: {
    captions: [
      'the clutch nobody asked for but everybody needed',
      'speedrun attempt #247, this is the one (it was not the one)',
      'when the boss has a second phase you didn\'t know about',
      'explaining a frame-perfect trick in the slowest way possible',
      'my controller after that loss vs before',
      'the glitch that saved my whole run, patch this never',
    ],
    tags: ['gaming', 'gamingtiktok', 'speedrun', 'gamer', 'twitchclips', 'gamingclips'],
  },
  nature: {
    captions: [
      'found a waterfall that\'s not on any map I could find',
      'identifying every mushroom on this trail (safely, from a distance)',
      'the sunrise that made the 4am alarm worth it',
      'this switchback view stopped the whole group in their tracks',
      'trail conditions after 3 days of rain, bring gaiters',
      'a whole field of these appeared overnight, nature is unreal',
    ],
    tags: ['nature', 'hiking', 'trailrunning', 'outdoors', 'pnw', 'explorepage'],
  },
  fashion: {
    captions: [
      'thrifted this for $6, styled 3 ways for under $30 total',
      'the layering trick that makes any outfit look intentional',
      'closet clean-out: keep, donate, or sell?',
      'recreating a runway look on a real-person budget',
      'capsule wardrobe update: 12 pieces, endless outfits',
      'the accessory that instantly elevates a basic fit',
    ],
    tags: ['fashion', 'thriftflip', 'ootd', 'styletok', 'budgetfashion', 'thrifted'],
  },
  dance: {
    captions: [
      'learned this in one afternoon, don\'t look too closely at count 3',
      'the transition at 0:12 took us 40 takes',
      'teaching the choreo in slow-mo so you can actually follow',
      'studio session got chaotic, keep the bloopers or nah?',
      'five dancers, one 8-count, zero rehearsal (lie, so much rehearsal)',
      'freestyle friday, no cuts no cap',
    ],
    tags: ['dance', 'choreography', 'dancetok', 'dancecrew', 'freestyle'],
  },
};

const SOUND_NAMES = [
  'original sound', 'Aesthetic (slowed)', 'lofi study beat', 'trending remix v2',
  'golden hour', 'main character energy', 'viral audio #4', 'soft piano loop',
  'upbeat summer mix', 'y2k nostalgia',
];

const COMMENT_POOL = [
  'okay this is actually so good 😭', 'wait the ending got me', 'no because I NEEDED this today',
  'the algorithm knew exactly what it was doing sending me here', 'saving this for later 📌',
  'not me watching this 4 times in a row', 'the way I gasped', 'tutorial please??',
  'this is so underrated, how is this not blowing up', 'sending this to everyone I know',
  'the effort put into this 👏👏👏', 'okay but the transition tho', 'this fixed my whole week honestly',
  'wait this actually works?? trying it now', 'the audio is SENT', 'first', 'real',
  'why did this hit so hard', 'not the plot twist at the end 💀', 'bookmarking this immediately',
];

const REPLY_POOL = [
  'right?? I was not ready', 'literally same', 'wait fr', 'lmaooo stop', '100%',
  'came here to say this', 'exactly what I said out loud alone in my room',
];

function daysAgo(n, offsetMinutes) {
  return Date.now() - n * 86400000 - offsetMinutes * 60000;
}

function seedIfEmpty(db) {
  return db.mutate((state) => {
    if (state.users.length > 0) return { seeded: false };

    // --- sounds -----------------------------------------------------
    SOUND_NAMES.forEach((name, i) => {
      state.sounds.push({
        id: db.nextId('snd'),
        name,
        seedUses: int(400, 850000),
        createdAt: daysAgo(120 - i, 0),
      });
    });

    // --- users --------------------------------------------------------
    const passwordHash = hashPassword('password123');
    USERS.forEach((u) => {
      state.users.push({
        id: db.nextId('u'),
        username: u.username,
        displayName: u.displayName,
        bio: u.bio,
        avatarSeed: u.avatarSeed,
        verified: u.verified,
        passwordHash,
        seedFollowers: int(1200, 4200000),
        seedFollowing: int(20, 340),
        createdAt: daysAgo(int(90, 400), 0),
        isSeed: true,
      });
    });

    const userByName = Object.fromEntries(state.users.map((u) => [u.username, u]));

    // --- videos + comments ---------------------------------------------
    let dayCursor = 0;
    USERS.forEach((u, ui) => {
      const theme = THEME_CONTENT[u.theme];
      const author = userByName[u.username];
      const n = 3;
      for (let i = 0; i < n; i++) {
        dayCursor += rand() * 1.6;
        const caption = theme.captions[i % theme.captions.length];
        const extraTags = [];
        // sprinkle a couple of caption-derived hashtags directly in the text
        const chosenTags = [pick(theme.tags), pick(theme.tags), pick(theme.tags)];
        const uniqueTags = Array.from(new Set(chosenTags));
        const hashtagSuffix = uniqueTags.map((t) => `#${t}`).join(' ');
        const fullCaption = `${caption} ${hashtagSuffix}`;
        const sound = rand() < 0.4
          ? { id: null, name: `original sound - ${u.username}` }
          : pick(state.sounds);

        const video = {
          id: db.nextId('v'),
          authorId: author.id,
          caption: fullCaption,
          style: u.style,
          visualSeed: ui * 10 + i,
          soundId: sound.id,
          soundName: sound.id ? sound.name : sound.name,
          type: 'procedural',
          url: null,
          mimetype: null,
          seedLikes: int(300, 980000),
          views: int(2000, 4200000),
          shares: int(10, 12000),
          createdAt: daysAgo(dayCursor, int(0, 800)),
          isSeed: true,
        };
        state.videos.push(video);

        // seeded comments
        const commentCount = int(2, 6);
        const commenterPool = state.users.filter((x) => x.id !== author.id);
        const topLevelComments = [];
        for (let c = 0; c < commentCount; c++) {
          const commenter = pick(commenterPool);
          const comment = {
            id: db.nextId('c'),
            videoId: video.id,
            authorId: commenter.id,
            parentId: null,
            text: pick(COMMENT_POOL),
            seedLikes: int(0, 4200),
            createdAt: video.createdAt + int(5, 5000) * 60000,
            isSeed: true,
          };
          state.comments.push(comment);
          topLevelComments.push(comment);
        }
        // a couple of replies
        if (rand() < 0.6 && topLevelComments.length) {
          const parent = pick(topLevelComments);
          const replier = pick(commenterPool.concat([author]));
          state.comments.push({
            id: db.nextId('c'),
            videoId: video.id,
            authorId: replier.id,
            parentId: parent.id,
            text: pick(REPLY_POOL),
            seedLikes: int(0, 300),
            createdAt: parent.createdAt + int(2, 400) * 60000,
            isSeed: true,
          });
        }
      }
    });

    // a light seed social graph so a fresh account's "Following" feed has
    // somewhere to start once they follow a creator, and so follower counts
    // feel alive between seed accounts too.
    state.users.forEach((u) => {
      const others = state.users.filter((x) => x.id !== u.id);
      const followCount = int(1, 5);
      for (let i = 0; i < followCount; i++) {
        const target = pick(others);
        const exists = state.follows.some((f) => f.followerId === u.id && f.followingId === target.id);
        if (!exists) {
          state.follows.push({
            id: db.nextId('f'),
            followerId: u.id,
            followingId: target.id,
            createdAt: daysAgo(int(1, 200), 0),
            isSeed: true,
          });
        }
      }
    });

    return { seeded: true, users: state.users.length, videos: state.videos.length };
  });
}

module.exports = { seedIfEmpty };

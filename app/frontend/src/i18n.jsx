import { createContext, useContext, useEffect, useState } from "react";

// Every word the interface says, in both languages. The assistant answers in whatever
// language the question was asked in - this is only the chrome around it, so the two are
// independent on purpose: a Greek speaker can keep an English interface, or the reverse.

const STRINGS = {
  el: {
    brand: "Policy Assistant",
    fromCache: "από cache",
    fromCacheTitle: "Η ίδια ερώτηση είχε απαντηθεί ήδη — δεν ξοδεύτηκαν tokens",
    cacheTitle: "Αποθηκευμένες απαντήσεις",
    cacheNote: "Η ίδια ερώτηση δεν πληρώνεται δύο φορές",
    cacheEntries: (n) => `${n} απαντήσεις στο cache`,
    cacheHits: (n) => `${n} φορές σερβιρίστηκαν χωρίς κλήση στο μοντέλο`,
    clearCache: "Καθάρισμα cache",
    cacheCleared: (n) => `Διαγράφηκαν ${n} αποθηκευμένες απαντήσεις`,
    errorTitle: {
      rate_limit: "Εξαντλήθηκε το ημερήσιο όριο",
      auth: "Το κλειδί απορρίφθηκε",
      offline: "Δεν υπάρχει σύνδεση με το μοντέλο",
      no_model: "Το μοντέλο δεν είναι διαθέσιμο",
      failed: "Κάτι πήγε λάθος",
    },
    rateLimitBody: (model, wait) =>
      wait
        ? `Το ${model} έχει ξοδέψει τα tokens της ημέρας. Ξαναδοκίμασε σε ${wait} ή άλλαξε μοντέλο στο rag_demo/.env.`
        : `Το ${model} έχει ξοδέψει τα tokens της ημέρας. Το όριο ανανεώνεται αυτόματα — ή άλλαξε μοντέλο στο rag_demo/.env.`,
    rateLimitHint: "Οι ερωτήσεις που έχεις ήδη κάνει απαντιούνται κανονικά από το cache.",
    errorBody: {
      auth: "Ο Groq απέρριψε το κλειδί. Έλεγξε το GROQ_API_KEY στο rag_demo/.env.",
      offline: "Δεν ήταν δυνατή η επικοινωνία με το μοντέλο. Έλεγξε τη σύνδεσή σου.",
      no_model: (model) =>
        `Το ${model} δεν είναι διαθέσιμο με αυτό το κλειδί. Διάλεξε άλλο στο rag_demo/.env.`,
    },
    documentsView: "Έγγραφα",
    documentsTitle: "Τα έγγραφα του βοηθού",
    documentsSubtitle: "Ο βοηθός απαντά μόνο από αυτά. Πρόσθεσε ένα και είναι αμέσως διαθέσιμο.",
    dropHere: "Σύρε ένα έγγραφο εδώ",
    orBrowse: "ή πάτησε για επιλογή",
    supportedTypes: (list) => `Υποστηρίζονται: ${list}`,
    uploading: "Γίνεται ανάγνωση και δεικτοδότηση…",
    uploaded: (name, chunks) => `Το ${name} προστέθηκε σε ${chunks} αποσπάσματα`,
    replacedDoc: (name) => `Το ${name} αντικαταστάθηκε`,
    chunksCount: (count) => `${count} αποσπάσματα`,
    notIndexed: "δεν έχει δεικτοδοτηθεί",
    deleteDoc: "Αφαίρεση εγγράφου",
    deleteDocConfirm: (name) =>
      `Να αφαιρεθεί το ${name}; Θα σβηστεί από τον φάκελο και από τη βάση.`,
    noCost: "Τα embeddings υπολογίζονται τοπικά — δεν ξοδεύεται τίποτα.",
    helpful: "Βοήθησε",
    notHelpful: "Δεν βοήθησε",
    whyNot: "Τι δεν πήγε καλά;",
    thanks: "Καταγράφηκε",
    reason: {
      not_answered: "Δεν απάντησε στην ερώτησή μου",
      wrong: "Λάθος πληροφορία",
      incomplete: "Ελλιπής ή πολύ γενική",
      wrong_source: "Απάντησε από λάθος έγγραφο",
      refused_wrongly: "Αρνήθηκε αν και υπάρχει στα έγγραφα",
      language: "Λάθος γλώσσα ή κακή διατύπωση",
      other: "Άλλο",
    },
    helpfulRate: "Κρίθηκαν χρήσιμες",
    ratedOf: (rated) => `από ${rated} αξιολογημένες`,
    reasonsTitle: "Λόγοι αρνητικής αξιολόγησης",
    reasonsNote: "Ποσοστό επί των αρνητικών αξιολογήσεων",
    flaggedTitle: "Απαντήσεις που σημαδεύτηκαν",
    flaggedNote: "Οι τελευταίες, με τον λόγο που δηλώθηκε",
    noRatings: "Καμία αξιολόγηση ακόμη. Τα κουμπιά είναι κάτω από κάθε απάντηση.",
    byDepartment: "Ερωτήσεις ανά τμήμα",
    byDepartmentNote: "Το τμήμα βγαίνει από τα έγγραφα που βρήκε η αναζήτηση, όχι από τα λόγια της ερώτησης",
    department: {
      hr: "Ανθρώπινο δυναμικό",
      finance: "Οικονομικά",
      it: "Πληροφορική",
      facilities: "Εγκαταστάσεις",
      delivery: "Μηχανική",
      other: "Αταξινόμητα",
    },
    legendAnswered: "Απαντήθηκαν",
    legendRefused: "Δεν απαντήθηκαν",
    ofDepartment: (answered, refused) =>
      `${answered} απαντήθηκαν, ${refused} δεν απαντήθηκαν`,
    theme: "Θέμα",
    dark: "Σκούρο",
    light: "Φωτεινό",
    searching: "Αναζήτηση στα έγγραφα…",
    reading: "Σύνταξη απάντησης…",
    sourcesStrip: "Πηγές",
    today: "Σήμερα",
    yesterday: "Χθες",
    earlier: "Παλαιότερα",
    newChat: "Νέα συζήτηση",
    noConversations: "Καμία συζήτηση ακόμη. Ό,τι ρωτήσεις αποθηκεύεται και μένει εδώ.",
    rename: "Μετονομασία",
    delete: "Διαγραφή",
    renameLabel: "Νέο όνομα συζήτησης",
    deleteConfirm: (title) => `Να διαγραφεί η συζήτηση «${title}»;`,
    conversationsHeading: "Συζητήσεις",
    messages: (count) => `${count} μηνύματα`,
    chat: "Συζήτηση",
    dashboard: "Στατιστικά",
    language: "Γλώσσα",
    documents: (count) => `${count} έγγραφα`,
    chunkMethod: "Πώς κόβονται τα έγγραφα σε κομμάτια",
    topK: "Πόσα αποσπάσματα διαβάζει το μοντέλο",
    limit: "Πάνω από αυτή την απόσταση, αρνείται",
    limitShort: "όριο",
    close: "Κλείσιμο",
    welcomeTitle: "Ρώτησε για τις πολιτικές της εταιρείας",
    welcomeText:
      "Ο βοηθός απαντά μόνο από τα έγγραφα που του έχουν δοθεί και δείχνει κάθε πηγή, ώστε να μπορεί να ελεγχθεί.",
    examples: [
      "Πόσες μέρες ετήσια άδεια δικαιούμαι;",
      "Ποιος εγκρίνει δαπάνη 7000 ευρώ;",
      "Χρειάζομαι απόδειξη για ταξί 30 ευρώ;",
      "What is the hotel limit in London?",
    ],
    placeholder: "Ρώτησε για τις πολιτικές της εταιρείας…",
    composerNote: "Απαντά μόνο από τα έγγραφα που του έχουν δοθεί, στη γλώσσα που ρωτάς.",
    send: "Αποστολή",
    viewSources: "Δες τις πηγές",
    sourceTitle: (number) => `Πηγή ${number}`,
    refusalNote:
      "Δεν βρέθηκε στα έγγραφα. Ο βοηθός απαντά μόνο από αυτά, γι' αυτό δεν συμπληρώνει κάτι από μόνος του.",
    sources: "Πηγές",
    sourcesCount: (count) => `${count} αποσπάσματα δόθηκαν στο μοντέλο`,
    quoteHeading: "Η πρόταση που χρησιμοποίησε",
    checkHeading: "Ο έλεγχος που έκανε",
    searchedHeading: "Τι αναζητήθηκε",
    chunksHeading: "Τα αποσπάσματα",
    used: "χρησιμοποιήθηκε",
    apiMissing: (reason) => `Δεν βρέθηκε το API στο :8000 (${reason}). Τρέχει το uvicorn;`,

    statsTitle: "Στατιστικά χρήσης",
    statsSubtitle: "Υπολογισμένα από τις αποθηκευμένες συζητήσεις",
    statQuestions: "Ερωτήσεις",
    statAnswered: "Απαντήθηκαν",
    statRefused: "Δεν απαντήθηκαν",
    statCitation: "Με αναφορά πηγής",
    statConversations: (count) => `σε ${count} συζητήσεις`,
    ofQuestions: "των ερωτήσεων",
    ofAnswers: "των απαντήσεων",
    answerRate: "Ποσοστό απάντησης",
    citationRate: "Ποσοστό με αναφορά",
    topQuestions: "Πιο συχνές ερωτήσεις",
    topQuestionsNote: "Ίδια ερώτηση με ή χωρίς τόνους μετριέται μία φορά",
    times: (count) => (count === 1 ? "1 φορά" : `${count} φορές`),
    unanswered: "Ερωτήσεις που δεν απαντήθηκαν",
    unansweredNote: "Αυτές δείχνουν τι λείπει από τα έγγραφα",
    citedFiles: "Έγγραφα που χρησιμοποιήθηκαν",
    activity: "Ερωτήσεις ανά ημέρα",
    activityNote: "Τελευταίες 14 ημέρες",
    questionsOn: (count, day) => `${day}: ${count} ερωτήσεις`,
    noData: "Δεν υπάρχουν ακόμη δεδομένα. Κάνε μερικές ερωτήσεις πρώτα.",
    perfect: "όλες οι απαντήσεις είχαν αναφορά",
  },

  en: {
    brand: "Policy Assistant",
    fromCache: "from cache",
    fromCacheTitle: "This exact question was answered before - no tokens were spent",
    cacheTitle: "Cached answers",
    cacheNote: "The same question is not paid for twice",
    cacheEntries: (n) => `${n} answers cached`,
    cacheHits: (n) => `served ${n} times without a model request`,
    clearCache: "Clear the cache",
    cacheCleared: (n) => `Dropped ${n} cached answers`,
    errorTitle: {
      rate_limit: "The daily token budget is spent",
      auth: "The API key was refused",
      offline: "The model cannot be reached",
      no_model: "That model is not available",
      failed: "Something went wrong",
    },
    rateLimitBody: (model, wait) =>
      wait
        ? `${model} has spent today's tokens. Try again in ${wait}, or change the model in rag_demo/.env.`
        : `${model} has spent today's tokens. The budget refreshes on its own - or change the model in rag_demo/.env.`,
    rateLimitHint: "Questions you have already asked are still answered, from the cache.",
    errorBody: {
      auth: "Groq refused the key. Check GROQ_API_KEY in rag_demo/.env.",
      offline: "The model could not be reached. Check your connection.",
      no_model: (model) =>
        `${model} is not available on this key. Choose another in rag_demo/.env.`,
    },
    documentsView: "Documents",
    documentsTitle: "The assistant's documents",
    documentsSubtitle: "It answers only from these. Add one and it is available at once.",
    dropHere: "Drop a document here",
    orBrowse: "or click to choose one",
    supportedTypes: (list) => `Supported: ${list}`,
    uploading: "Reading and indexing…",
    uploaded: (name, chunks) => `${name} added as ${chunks} extracts`,
    replacedDoc: (name) => `${name} was replaced`,
    chunksCount: (count) => `${count} extracts`,
    notIndexed: "not indexed",
    deleteDoc: "Remove document",
    deleteDocConfirm: (name) =>
      `Remove ${name}? It will be deleted from the folder and from the database.`,
    noCost: "Embeddings are computed locally - this costs nothing.",
    helpful: "Helpful",
    notHelpful: "Not helpful",
    whyNot: "What went wrong?",
    thanks: "Recorded",
    reason: {
      not_answered: "It did not answer my question",
      wrong: "The information is wrong",
      incomplete: "Incomplete or too general",
      wrong_source: "Answered from the wrong document",
      refused_wrongly: "Refused although the documents cover it",
      language: "Wrong language or badly worded",
      other: "Something else",
    },
    helpfulRate: "Rated helpful",
    ratedOf: (rated) => `of ${rated} rated`,
    reasonsTitle: "Why answers were unhelpful",
    reasonsNote: "Share of the negative ratings",
    flaggedTitle: "Flagged answers",
    flaggedNote: "The most recent, with the reason given",
    noRatings: "No ratings yet. The buttons are under every answer.",
    byDepartment: "Questions by department",
    byDepartmentNote: "The department comes from the documents the search found, not from the wording of the question",
    department: {
      hr: "People",
      finance: "Finance",
      it: "IT",
      facilities: "Facilities",
      delivery: "Engineering",
      other: "Unattributed",
    },
    legendAnswered: "Answered",
    legendRefused: "Not answered",
    ofDepartment: (answered, refused) => `${answered} answered, ${refused} not answered`,
    theme: "Theme",
    dark: "Dark",
    light: "Light",
    searching: "Searching the documents…",
    reading: "Writing the answer…",
    sourcesStrip: "Sources",
    today: "Today",
    yesterday: "Yesterday",
    earlier: "Earlier",
    newChat: "New conversation",
    noConversations: "No conversations yet. Everything you ask is saved and stays here.",
    rename: "Rename",
    delete: "Delete",
    renameLabel: "New conversation name",
    deleteConfirm: (title) => `Delete the conversation “${title}”?`,
    conversationsHeading: "Conversations",
    messages: (count) => `${count} messages`,
    chat: "Chat",
    dashboard: "Dashboard",
    language: "Language",
    documents: (count) => `${count} documents`,
    chunkMethod: "How the documents are cut into chunks",
    topK: "How many chunks the model reads",
    limit: "Further away than this and it refuses",
    limitShort: "limit",
    close: "Close",
    welcomeTitle: "Ask about the company policies",
    welcomeText:
      "The assistant answers only from the documents it was given, and shows every source so the answer can be checked.",
    examples: [
      "How many days of annual leave do I get?",
      "Who approves an expense of 7000 euros?",
      "Do I need a receipt for a 30 euro taxi?",
      "Πόσες μέρες ετήσια άδεια δικαιούμαι;",
    ],
    placeholder: "Ask about the company policies…",
    composerNote:
      "Answers only from the documents it was given, in the language you ask in.",
    send: "Send",
    viewSources: "View sources",
    sourceTitle: (number) => `Source ${number}`,
    refusalNote:
      "Not found in the documents. The assistant answers only from them, so it does not fill in the rest itself.",
    sources: "Sources",
    sourcesCount: (count) => `${count} extracts were given to the model`,
    quoteHeading: "The sentence it relied on",
    checkHeading: "The comparison it made",
    searchedHeading: "What was searched for",
    chunksHeading: "The extracts",
    used: "used",
    apiMissing: (reason) => `No API on :8000 (${reason}). Is uvicorn running?`,

    statsTitle: "Usage statistics",
    statsSubtitle: "Counted from the stored conversations",
    statQuestions: "Questions",
    statAnswered: "Answered",
    statRefused: "Not answered",
    statCitation: "With a citation",
    statConversations: (count) => `across ${count} conversations`,
    ofQuestions: "of questions",
    ofAnswers: "of answers",
    answerRate: "Answer rate",
    citationRate: "Citation rate",
    topQuestions: "Most frequent questions",
    topQuestionsNote: "The same question with or without accents counts once",
    times: (count) => (count === 1 ? "once" : `${count} times`),
    unanswered: "Questions that were not answered",
    unansweredNote: "These show what the documents are missing",
    citedFiles: "Documents actually used",
    activity: "Questions per day",
    activityNote: "Last 14 days",
    questionsOn: (count, day) => `${day}: ${count} questions`,
    noData: "No data yet. Ask a few questions first.",
    perfect: "every answer carried a citation",
  },
};

const LanguageContext = createContext({ language: "el", strings: STRINGS.el });

export function LanguageProvider({ children }) {
  const [language, setLanguage] = useState(() => {
    // A remembered preference, which is exactly what browser storage is for. It can
    // come back empty or throw in a private window, so the default stands on its own.
    try {
      return localStorage.getItem("ui-language") === "en" ? "en" : "el";
    } catch {
      return "el";
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem("ui-language", language);
    } catch {
      /* nothing to do - the choice simply will not be remembered */
    }
    document.documentElement.lang = language;
  }, [language]);

  return (
    <LanguageContext.Provider
      value={{ language, setLanguage, strings: STRINGS[language] }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}

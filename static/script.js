/***********************************************************
 * script.js - Manages:
 *  1) Only one <details> open at a time
 *  2) Word-by-word + line-by-line animation for messages
 *  3) Bolding text between *...*
 *  4) Gathering resources & sending them to Flask (or any backend)
 *  5) UI logic for Summarize, Ask, End Conversation
 ***********************************************************/

// DOM references
const chatMessages = document.getElementById('chatMessages');
const usernameField = document.getElementById('username');
const questionInput = document.getElementById('questionInput');

// Resource fields
const youtubeFields = [
  document.getElementById('youtube1'),
  document.getElementById('youtube2'),
  document.getElementById('youtube3')
];
const websiteFields = [
  document.getElementById('website1'),
  document.getElementById('website2'),
  document.getElementById('website3')
];
const wikiFields = [
  document.getElementById('wiki1'),
  document.getElementById('wiki2'),
  document.getElementById('wiki3')
];
const fileFields = [
  document.getElementById('file1'),
  document.getElementById('file2'),
  document.getElementById('file3')
];
const audioFields = [
  document.getElementById('audio1'),
  document.getElementById('audio2'),
  document.getElementById('audio3')
];
const videoFields = [
  document.getElementById('video1'),
  document.getElementById('video2'),
  document.getElementById('video3')
];

// Buttons
const askButton = document.getElementById('askButton');
const summarizeButton = document.getElementById('summarizeButton');
const endConversationButton = document.getElementById('endConversationButton');

// 1) Only one <details> open at a time
const allDetails = document.querySelectorAll('details');
allDetails.forEach((dt) => {
  dt.addEventListener('toggle', function() {
    if (this.open) {
      // Close others
      allDetails.forEach((other) => {
        if (other !== this && other.open) {
          other.open = false;
        }
      });
    }
  });
});

/************************************************
 * Helper: Type out text word-by-word & line-by-line
 * Also detect any *bold* segments
 ***********************************************/
async function typeMessage(container, text) {
  // Split text into lines
  const lines = text.split('\n');

  for (let l = 0; l < lines.length; l++) {
    const line = lines[l].trim();
    if (!line) {
      // Just add a line break if empty
      container.appendChild(document.createElement('br'));
      continue;
    }

    // Split line by spaces to get words
    const words = line.split(' ');

    for (let w = 0; w < words.length; w++) {
      // Check for *bold* pattern
      const processedWord = processBoldSyntax(words[w]);
      
      // Append word to container
      container.appendChild(processedWord);
      if (w < words.length - 1) {
        container.appendChild(document.createTextNode(' '));
      }

      // Delay
      await delay(35); // 35ms between words
    }

    // End line
    if (l < lines.length - 1) {
      container.appendChild(document.createElement('br'));
      await delay(100); // short pause before next line
    }
  }
}

// Process any *...* pattern to <strong> tags
function processBoldSyntax(word) {
  // Simple approach: if word starts with * and ends with *, remove them and wrap in <strong>
  if (word.startsWith('*') && word.endsWith('*') && word.length > 1) {
    const stripped = word.slice(1, -1);
    const strongEl = document.createElement('strong');
    strongEl.textContent = stripped;
    return strongEl;
  } else {
    // For inline usage, check with a regex
    const pattern = /\*(.*?)\*/;
    const match = word.match(pattern);
    if (match) {
      // separate text around the match
      const before = word.slice(0, match.index);
      const bolded = match[1];
      const after = word.slice(match.index + match[0].length);

      const spanEl = document.createElement('span');
      if (before) spanEl.appendChild(document.createTextNode(before));
      const strongEl = document.createElement('strong');
      strongEl.textContent = bolded;
      spanEl.appendChild(strongEl);
      if (after) spanEl.appendChild(document.createTextNode(after));

      return spanEl;
    }
    // no bold syntax
    return document.createTextNode(word);
  }
}

// Delay utility
function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/*****************************************
 * Add message to chat with animation
 *****************************************/
async function addMessageToChat(sender, fullText) {
  // Create the .message wrapper
  const messageEl = document.createElement('div');
  messageEl.classList.add('message', sender);

  // Create the bubble
  const bubbleEl = document.createElement('div');
  bubbleEl.classList.add('bubble');
  messageEl.appendChild(bubbleEl);

  // Append to chat first (empty bubble)
  chatMessages.appendChild(messageEl);

  // Type out the text into the bubble
  await typeMessage(bubbleEl, fullText);

  // Auto-scroll
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

/*****************************************************
 * Add a loading message to the chat
 *****************************************************/
function addLoadingMessage() {
  // Create the .message wrapper
  const messageEl = document.createElement('div');
  messageEl.classList.add('message', 'assistant');

  // Create the bubble
  const bubbleEl = document.createElement('div');
  bubbleEl.classList.add('bubble');

  // Create the video element
  const loadingVideo = document.createElement('video');
  loadingVideo.src = 'static/mp4_icons/Chatbot (1).mp4'; // Ensure this path is correct
  loadingVideo.autoplay = true;
  loadingVideo.loop = true;
  loadingVideo.muted = true;
  loadingVideo.playsInline = true;
  loadingVideo.classList.add('loading-video');

  // Append the video to the bubble
  bubbleEl.appendChild(loadingVideo);
  messageEl.appendChild(bubbleEl);

  // Append to chat
  chatMessages.appendChild(messageEl);

  // Auto-scroll
  chatMessages.scrollTop = chatMessages.scrollHeight;

  return bubbleEl;
}

/*****************************************************
 * Collect resources into FormData
 *****************************************************/
function gatherResourcesFormData() {
  const formData = new FormData();
  formData.append('username', usernameField.value.trim());

  // YouTube links
  youtubeFields.forEach((field, idx) => {
    if (field.value.trim()) {
      formData.append(`youtube_link${idx+1}`, field.value.trim());
    }
  });
  // Website URLs
  websiteFields.forEach((field, idx) => {
    if (field.value.trim()) {
      formData.append(`website_url${idx+1}`, field.value.trim());
    }
  });
  // Wikipedia Titles
  wikiFields.forEach((field, idx) => {
    if (field.value.trim()) {
      formData.append(`wikipedia_title${idx+1}`, field.value.trim());
    }
  });
  // Files
  fileFields.forEach((input, idx) => {
    if (input.files.length > 0) {
      formData.append(`uploaded_file${idx+1}`, input.files[0]);
    }
  });
  // Audio
  audioFields.forEach((input, idx) => {
    if (input.files.length > 0) {
      formData.append(`uploaded_file_audio${idx+1}`, input.files[0]);
    }
  });
  // Video
  videoFields.forEach((input, idx) => {
    if (input.files.length > 0) {
      formData.append(`uploaded_file_video${idx+1}`, input.files[0]);
    }
  });

  return formData;
}

/***************************************************
 * Handle Ask Action
 **************************************************/
async function handleAsk() {
  const username = usernameField.value.trim();
  const question = questionInput.value.trim();
  if (!username) {
    alert("Please enter a username before asking a question.");
    return;
  }
  if (!question) {
    alert("Please enter a question.");
    return;
  }

  // Add user question in chat
  await addMessageToChat('user', question);

  // Clear the question input box
  questionInput.value = '';

  // Add loading message and keep a reference to the bubble
  const loadingBubble = addLoadingMessage();

  const formData = gatherResourcesFormData();
  formData.append('question', question);

  try {
    // Example fetch to your backend
    const response = await fetch('/api/ask_question', {
      method: 'POST',
      body: formData
    });
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to get an answer.');
    }
    const data = await response.json();
    const { answer } = data;

    // Remove the loading video
    loadingBubble.innerHTML = ''; // Clear the bubble

    // Type out the answer
    await typeMessage(loadingBubble, answer);

    // Auto-scroll
    chatMessages.scrollTop = chatMessages.scrollHeight;
  } catch (err) {
    // Remove the loading video
    loadingBubble.innerHTML = '';

    // Display error message
    await addMessageToChat('assistant', 'Error answering: ' + err.message);
  }
}

/***************************************************
 * Summarize Handler
 **************************************************/
summarizeButton.addEventListener('click', async () => {
  const username = usernameField.value.trim();
  if (!username) {
    alert("Please enter a username before summarizing.");
    return;
  }

  // Inform user in chat
  await addMessageToChat('user', '[Requesting summary for the provided resources...]');

  const formData = gatherResourcesFormData();

  const loadingBubble = addLoadingMessage();
  
  try {
    // Example fetch to your backend
    const response = await fetch('/api/summary', {
      method: 'POST',
      body: formData
    });
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to get summary.');
    }
    const data = await response.json();
    const { summary } = data;

    // Display the summary
    await addMessageToChat('assistant', summary);

    // Check for unsupported resources
    const {
      unsupported_youtube_links,
      unsupported_files,
      unsupported_websites,
      unsupported_wikipedia_titles
    } = data;

    const errorMessage = [];
    if (unsupported_youtube_links?.length) {
      errorMessage.push('Unsupported YouTube links: ' + unsupported_youtube_links.join(', '));
    }
    if (unsupported_files?.length) {
      errorMessage.push('Unsupported files: ' + unsupported_files.join(', '));
    }
    if (unsupported_websites?.length) {
      errorMessage.push('Unsupported websites: ' + unsupported_websites.join(', '));
    }
    if (unsupported_wikipedia_titles?.length) {
      errorMessage.push('Unsupported Wikipedia titles: ' + unsupported_wikipedia_titles.join(', '));
    }
    if (errorMessage.length) {
      await addMessageToChat('assistant', 'Some resources were not processed:\n' + errorMessage.join('\n'));
    }
  } catch (err) {
    await addMessageToChat('assistant', 'Error summarizing: ' + err.message);
  }
});

/***************************************************
 * Ask Question Handler
 **************************************************/
// Attach handleAsk to Ask button click
askButton.addEventListener('click', handleAsk);

// Add event listener to questionInput for Enter key
questionInput.addEventListener('keydown', function(e) {
  if (e.key === 'Enter') {
    e.preventDefault(); // Prevent any default behavior
    handleAsk();
  }
});

/***************************************************
 * End Conversation Handler
 **************************************************/
endConversationButton.addEventListener('click', async () => {
  const username = usernameField.value.trim();
  if (!username) {
    alert("Please enter a username before ending conversation.");
    return;
  }

  try {
    // Example fetch to your backend
    const response = await fetch('/api/end_conversation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username })
    });
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to end conversation.');
    }

    // Clear the chat area
    chatMessages.innerHTML = '';
    await addMessageToChat('assistant', `Conversation ended for user '${username}'.\nIn-memory data cleared.`);

    // Optionally clear resource fields
    youtubeFields.forEach(field => field.value = '');
    websiteFields.forEach(field => field.value = '');
    wikiFields.forEach(field => field.value = '');
    fileFields.forEach(input => { input.value = ''; });
    audioFields.forEach(input => { input.value = ''; });
    videoFields.forEach(input => { input.value = ''; });
    questionInput.value = '';
  } catch (err) {
    await addMessageToChat('assistant', 'Error: ' + err.message);
  }
});

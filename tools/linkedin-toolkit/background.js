// background.js — Antek LinkedIn Toolkit
chrome.runtime.onInstalled.addListener(() => {
  console.log('Antek LinkedIn Toolkit installed');
  chrome.storage.local.get({ savedUrls: [], prospects: [], groupPosts: [] }, data => {
    chrome.storage.local.set({
      savedUrls: data.savedUrls || [],
      prospects: data.prospects || [],
      groupPosts: data.groupPosts || []
    });
  });
});

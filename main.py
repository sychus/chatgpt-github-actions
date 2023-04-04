# Automated Code Review using the ChatGPT language model

# Import statements
import argparse
import openai
import os
import requests
from github import Github

# Adding command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--openai_api_key', help='Your OpenAI API Key')
parser.add_argument('--github_token', help='Your Github Token')
parser.add_argument('--github_pr_id', help='Your Github PR ID')
parser.add_argument('--openai_engine', default="text-davinci-002",
                    help='GPT-3 model to use. Options: text-davinci-002, text-babbage-001, text-curie-001, text-ada-001')
parser.add_argument('--openai_temperature', default=0.5,
                    help='Sampling temperature to use. Higher values means the model will take more risks. Recommended: 0.5')
parser.add_argument('--openai_max_tokens', default=2048,
                    help='The maximum number of tokens to generate in the completion.')
parser.add_argument('--mode', default="files",
                    help='PR interpretation form. Options: files, patch')
args = parser.parse_args()

# Authenticating with the OpenAI API
openai.api_key = args.openai_api_key

# Authenticating with the Github API
g = Github(args.github_token)


def files():
    repo = g.get_repo(os.getenv('GITHUB_REPOSITORY'))
    pull_request = repo.get_pull(int(args.github_pr_id))

    # Loop through the commits in the pull request
    commits = pull_request.get_commits()
    for commit in commits:
        # Getting the modified files in the commit
        files = commit.files
        for file in files:
            # Getting the file name and content
            filename = file.filename
            content = repo.get_contents(
                filename, ref=commit.sha).decoded_content

            # Sending the code to ChatGPT
            response = openai.Completion.create(
                engine=args.openai_engine,
                prompt=(
                    f"Review this code patch and suggest improvements and issues:\n```{content}```"),
                temperature=float(args.openai_temperature),
                max_tokens=int(args.openai_max_tokens)
            )

            # Adding a comment to the pull request with ChatGPT's response
            pull_request.create_issue_comment(
                f"ChatGPT's response about `{file.filename}`:\n {response['choices'][0]['text']}")


def patch():
    repo = g.get_repo(os.getenv('GITHUB_REPOSITORY'))
    pull_request = repo.get_pull(int(args.github_pr_id))

    content = get_content_patch()

    if len(content) == 0:
        pull_request.create_issue_comment(
            f"Patch file does not contain any changes")
        return

    parsed_text = content.split("diff")

    for diff_text in parsed_text:
        if len(args.openai_max_tokens) == 0:
            continue

        try:
            file_name = diff_text.split("b/")[1].splitlines()[0]
            print(file_name)
            parts = [diff_text[i:i+args.openai_max_tokens]
                     for i in range(0, len(diff_text), args.openai_max_tokens)]
            full_response = ""
            text_parts = []
            for part in parts:
                response = openai.Completion.create(
                    engine=args.openai_engine,
                    prompt=(
                        f"Summarize what was done in this diff:\n```{part}```"),
                    max_tokens=int(args.openai_max_tokens),
                    n=1,
                    stop=None,
                    temperature=float(args.openai_temperature)
                )
            text_parts.append(response.choices[0].text)
            full_response = ''.join(text_parts)
            print(full_response)
            print(full_response['choices'][0]['text'])

            pull_request.create_issue_comment(
                f"ChatGPT's response about ``{file_name}``:\n {full_response['choices'][0]['text']}")
        except Exception as e:
            error_message = str(e)
            print(error_message)
            pull_request.create_issue_comment(
                f"ChatGPT was unable to process the response about {file_name}")


def get_content_patch():
    url = f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY')}/pulls/{args.github_pr_id}"
    print(url)

    headers = {
        'Authorization': f"token {args.github_token}",
        'Accept': 'application/vnd.github.v3.diff'
    }

    response = requests.request("GET", url, headers=headers)

    if response.status_code != 200:
        raise Exception(response.text)

    return response.text


if (args.mode == "files"):
    files()

if (args.mode == "patch"):
    patch()

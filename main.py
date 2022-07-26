import os
import re
import time

import praw
import praw.models
import pymongo

# connect to mongoDB, first
# local client, local db, local collection, can edit if needed.
client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client['besties']
collection = db['raw_besties']

# connect to reddit
reddit = praw.Reddit(
    client_id=os.environ['REDDIT_CLIENT_ID'],
    client_secret=os.environ['REDDIT_CLIENT_SECRET'],
    user_agent=os.environ['REDDIT_USER_AGENT'],
    username=os.environ['REDDIT_USERNAME'],
    password=os.environ['REDDIT_PASSWORD']
)


def get_all_besties(user: str):
    """
    Function to get the db_best of a user.
    :param user: The user to get the db_best of.
    :return: A dictionary of db_best and their counts.
    """
    # get the db_best from the mongoDB
    db_besties = collection.find_one({'commenter': re.compile(user, re.IGNORECASE)})['besties']

    # sort the db_best by their count, descending.
    all_besties = {k: v for k, v in sorted(db_besties.items(), key=lambda item: item[1])}

    return all_besties


def main():
    # track startup time, so we don't reply to stale comments posted before the bot was started
    startup_time = time.time()

    # get arr neoliberal
    nl: praw.models.Subreddit = reddit.subreddit('neoliberal')

    # get the comments from the subreddit
    for comment in nl.stream.comments():  # type: praw.models.Comment
        record_comment(comment, startup_time)
        handle_comment(comment, startup_time)


def record_comment(comment: praw.models.Comment, startup_time: float):
    """
    Function to record the comment in the mongoDB.
    :param startup_time: Time the bot was started.
    :param comment: A reddit comment from the stream.
    :return: None
    """

    # check if comment is newer than the bot startup time.
    if comment.created_utc > startup_time:
        # check if comment is top level
        if isinstance(comment.parent(), praw.models.Submission):
            return
        # check if comment is by a user
        if comment.author is None:
            return
        # get the author of the comment.
        author = comment.author.name

        # check if the author is in the mongoDB
        if collection.find_one({'commenter': author}) is None:
            # create a new entry for the author
            collection.insert_one({
                'commenter': author,
                'besties': {}
            })
            print(f'Created new entry for {author}')

        # see if the comment has replied to a comment
        if isinstance(comment.parent(), praw.models.Comment):
            # get parent comment's author

            # check if the author is not None
            if comment.parent().author is not None:
                parent_author = comment.parent().author.name
                # check if parent in besties of author
                if parent_author not in collection.find_one({'commenter': author})['besties']:
                    # add parent to besties of author
                    collection.update_one({'commenter': author}, {'$set': {f'besties.{parent_author}': 1}})
                    print(f'Added {parent_author} to {author}\'s besties')
                else:
                    # increment the count of the parent
                    collection.update_one({'commenter': author}, {'$inc': {f'besties.{parent_author}': 1}})
                    print(f'Incremented {parent_author} count for {author}')


# noinspection GrazieInspection
def handle_comment(comment: praw.models.Comment, startup_time: float):
    """
    Function to handle responses to comment that comes in via stream.
    :param startup_time: Time the bot was started.
    :param comment: A reddit comment from the stream.
    :return: None
    """

    # first, check if the comment is newer than the bot startup time.
    if comment.created_utc > startup_time:
        # check if created by a user
        if comment.author is None:
            return
        # get the author of the comment.
        author: str = comment.author.name

        # !my_bestie command
        if '!my_bestie' in comment.body.lower():
            # log the command execution
            print(f'Responding to comment by: {author}, body: {comment.body}')
            try:
                # get the db_best of the author
                all_besties = get_all_besties(author)
                total_comments = sum(all_besties.values())

                # get the top 3 besties, iterate three times on all_besties as all_besties is sorted.
                top_besties = {}
                for i in range(3):
                    try:
                        bestie = all_besties.popitem()
                    except Exception as e:
                        print(f'Error: {e}')
                    top_besties[bestie[0]] = bestie[1]

                # create the response
                response = f'{author}, your top besties are:\n\n'
                for bestie in top_besties:
                    response += f'- {bestie}: {top_besties[bestie]}\n\n'
                response += f'{author}, you have made {total_comments} comments in total, therefore, you have made ' \
                            f'{round(sum(top_besties.values()) / total_comments * 100, 2)}% ' \
                            f'of your comments with your top three besties. ' \
                            f'You have made {round(list(top_besties.values())[0] / total_comments * 100, 2)}' \
                            f'% of your comments' \
                            f' with your ' \
                            f'top bestie, {list(top_besties.keys())[0]}.\n\n' \
                            f'You have interacted with {len(all_besties)} unique users.'

                # send the response
                comment.reply(response)
            except Exception as e:
                print(f'Error: {e}')
        elif '!their_bestie(' in comment.body.lower():
            # log the command execution
            print(f'Responding to comment by: {author}, body: {comment.body}')
            # get user mentioned in command:
            user = comment.body.lower().split('!their_bestie(')[1].split(')')[0]
            # get the db_best of the user
            try:
                all_besties = get_all_besties(user)
                total_comments = sum(all_besties.values())

                # get the top 3 besties, iterate three times on all_besties as all_besties is sorted.
                top_besties = {}
                for i in range(3):
                    bestie = all_besties.popitem()
                    top_besties[bestie[0]] = bestie[1]

                # create the response
                response = f'{user}\'s top besties are:\n\n'
                for bestie in top_besties:
                    response += f'- {bestie}: {top_besties[bestie]}\n\n'
                response += f'{user} has made {total_comments} comments in total, making them make ' \
                            f'{round(sum(top_besties.values()) / total_comments * 100, 2)}% ' \
                            f'of their comments with their top three besties. ' \
                            f'They have made {round(list(top_besties.values())[0] / total_comments * 100, 2)}' \
                            f'% of their comments with their    ' \
                            f'top bestie, {list(top_besties.keys())[0]}.\n\n' \
                            f'They have interacted with {len(all_besties)} unique users.'
                comment.reply(response)
            except Exception as e:
                print(f'Error: {e}')


if __name__ == '__main__':
    main()

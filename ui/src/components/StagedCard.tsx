import { CardBody } from "~/components/CardBody";
import type { TCardBox } from "~/data/boardModel";
import type { TCardFolds } from "~/lib/folds";
import {
  FrameMode,
  findBodyClass,
  findFrameStyle,
  findMarkdownClass,
} from "~/lib/frame";

const openFolds: TCardFolds = {
  label: "card on the stage",
  toggleCard: () => undefined,
  sections: [],
  toggleSection: () => undefined,
};

/** The card's frame as the whiteboard lays an open card out, with nothing folded and no changes shown. */
export const StagedCard = ({ md, width, height, versions }: TCardBox) => (
  <article
    style={findFrameStyle(FrameMode.enum.open, {
      place: { x: 0, y: 0 },
      width,
      height,
      layer: 0,
    })}
    className="absolute flex flex-col"
  >
    <div className={findBodyClass(FrameMode.enum.open)}>
      <div className={findMarkdownClass(versions)}>
        <CardBody
          md={md}
          before={null}
          diffStyle="word"
          toggle={() => undefined}
          folds={openFolds}
        />
      </div>
    </div>
  </article>
);
